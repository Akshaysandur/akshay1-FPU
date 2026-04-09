from __future__ import annotations

import json
import threading
import time
from collections import deque
from copy import deepcopy
from datetime import datetime
from math import hypot
from typing import Any

import paho.mqtt.client as mqtt

from dashboard.config import AMR_DRAW_OFFSETS, AMR_SPEED_PX, PATH_COORDINATES, PATH_GRAPH, STATIONS
from dashboard.models import AMRState, AlertEvent, DashboardState, Job
from dashboard.sample_data import build_initial_state


class DashboardMQTTClient:
    def __init__(self, broker: str, port: int, base_topic: str) -> None:
        self.broker = broker
        self.port = port
        self.base_topic = base_topic.rstrip("/")
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.lock = threading.Lock()
        self.state = build_initial_state()
        self.state.mqtt.broker = broker
        self.state.mqtt.port = port
        self.message_times: deque[float] = deque(maxlen=300)
        self.simulation_enabled = True
        self._connected_once = False
        self._last_tick = time.time()

    def start(self) -> None:
        try:
            self.client.connect(self.broker, self.port, keepalive=30)
            self.client.loop_start()
        except Exception as exc:
            with self.lock:
                self.state.mqtt.connected = False
                self.state.mqtt.last_error = str(exc)
                self._add_alert("Warning", f"MQTT broker unavailable, using simulation mode: {exc}")

    def stop(self) -> None:
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            pass

    def snapshot(self) -> DashboardState:
        with self.lock:
            self._simulate_if_needed()
            self.state.active_jobs = sum(1 for job in self.state.jobs.values() if job.status not in {"Completed", "Cancelled"})
            self.state.mqtt.message_rate = self._calculate_message_rate()
            return self._clone_state()

    def get_next_job_id(self) -> str:
        with self.lock:
            return f"{self.state.job_counter + 1:03d}"

    def publish_job(self, payload: dict[str, Any]) -> None:
        numeric_job_id = int(payload.get("job_id") or self.get_next_job_id())
        job = Job(
            job_id=f"{numeric_job_id:03d}",
            routing=payload["routing"],
            priority=payload["priority"],
            operations=payload.get("operations", []),
        )
        with self.lock:
            self.state.job_counter = max(self.state.job_counter, numeric_job_id)
            self.state.jobs[job.job_id] = job
            self._dispatch_jobs()
            self._add_alert("Info", f"Job {job.job_id} created from UI.")
        self._publish("jobs/create", payload)

    def publish_command(self, command: str, payload: dict[str, Any] | None = None) -> None:
        payload = payload or {}
        with self.lock:
            if command == "start":
                self.state.system_state = "Running"
                self._dispatch_jobs()
                self._add_alert("Info", "System start command issued.")
            elif command == "stop":
                self.state.system_state = "Stopped"
                self._add_alert("Warning", "System stop command issued.")
            elif command == "reset":
                broker = self.state.mqtt.broker
                port = self.state.mqtt.port
                self.state = build_initial_state()
                self.state.mqtt.broker = broker
                self.state.mqtt.port = port
                self._last_tick = time.time()
                self._add_alert("Info", "System reset command issued.")
        self._publish(f"system/{command}", payload)

    def publish_priority_update(self, job_id: str, priority: int) -> None:
        with self.lock:
            if job_id in self.state.jobs:
                self.state.jobs[job_id].priority = priority
                self._sync_scheduler_queue()
                self._add_alert("Info", f"Priority updated for {job_id}.")
        self._publish("jobs/priority", {"job_id": job_id, "priority": priority})

    def publish_manual_amr(self, amr_id: str, action: str) -> None:
        with self.lock:
            amr = self.state.amrs.get(amr_id)
            if amr:
                if action == "stop":
                    amr.route_nodes = []
                    amr.route_index = 0
                    amr.status = "Idle"
                    amr.current_task = f"Manual stop at {amr.location}"
                elif action == "move" and amr.location != "Loading":
                    amr.route_nodes = self._find_path(amr.location, "Loading")
                    amr.route_index = 1 if len(amr.route_nodes) > 1 else 0
                    amr.status = "Moving"
                    amr.current_task = "Manual return to Loading"
                self._sync_scheduler_queue()
                self._add_alert("Info", f"Manual AMR command sent: {amr_id} -> {action}.")
        self._publish("amr/manual", {"amr_id": amr_id, "action": action})

    def publish_reassign(self, amr_id: str, job_id: str) -> None:
        with self.lock:
            if job_id in self.state.jobs and amr_id in self.state.amrs:
                self._assign_job(self.state.jobs[job_id], self.state.amrs[amr_id], manual_override=True)
                self._add_alert("Warning", f"Manual task reassignment requested: {job_id} to {amr_id}.")
        self._publish("scheduler/reassign", {"amr_id": amr_id, "job_id": job_id})

    def _publish(self, topic_suffix: str, payload: dict[str, Any]) -> None:
        topic = f"{self.base_topic}/{topic_suffix}"
        try:
            self.client.publish(topic, json.dumps(payload), qos=0, retain=False)
        except Exception:
            pass

    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        with self.lock:
            self.state.mqtt.connected = True
            self.state.mqtt.last_update = datetime.now()
            self.state.mqtt.last_error = ""
            self._connected_once = True
            self._add_alert("Info", f"Connected to MQTT broker {self.broker}:{self.port}.")
        client.subscribe(f"{self.base_topic}/#")

    def _on_disconnect(self, client: mqtt.Client, userdata: Any, flags: Any, reason_code: Any, properties: Any) -> None:
        with self.lock:
            self.state.mqtt.connected = False
            self.state.mqtt.last_update = datetime.now()

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
        except json.JSONDecodeError:
            return
        with self.lock:
            self.message_times.append(time.time())
            self.state.mqtt.last_update = datetime.now()
            self._apply_message(msg.topic, payload)

    def _apply_message(self, topic: str, payload: dict[str, Any]) -> None:
        if topic.endswith("/status/system"):
            self.state.system_state = payload.get("system_state", self.state.system_state)
        elif topic.endswith("/status/amr"):
            amr_id = payload.get("amr_id", "AMR")
            amr = self.state.amrs.get(amr_id, AMRState(amr_id=amr_id))
            amr.status = payload.get("status", amr.status)
            amr.battery = payload.get("battery", amr.battery)
            amr.current_task = payload.get("current_task", amr.current_task)
            amr.location = payload.get("location", amr.location)
            amr.x = payload.get("x", amr.x)
            amr.y = payload.get("y", amr.y)
            self.state.amrs[amr_id] = amr
        elif topic.endswith("/scheduler/queue"):
            self.state.scheduler.queue = payload.get("queue", self.state.scheduler.queue)
            self.state.scheduler.allocations = payload.get("allocations", self.state.scheduler.allocations)
            self.state.scheduler.mode = payload.get("mode", self.state.scheduler.mode)
        elif topic.endswith("/alerts/event"):
            self._add_alert(payload.get("severity", "Info"), payload.get("message", "Event received."))

    def _simulate_if_needed(self) -> None:
        if not self.simulation_enabled:
            return
        self.message_times.append(time.time())
        self.state.mqtt.last_update = datetime.now()
        now = time.time()
        dt = min(now - self._last_tick, 1.0)
        self._last_tick = now
        self._dispatch_jobs()
        if self.state.system_state != "Running":
            return

        for amr in self.state.amrs.values():
            if amr.dwell_until and now < amr.dwell_until:
                amr.status = "Processing"
                amr.current_task = f"{amr.dwell_station}: processing"
                continue
            if amr.dwell_until and now >= amr.dwell_until:
                amr.dwell_until = 0.0
                amr.dwell_station = ""
                self._prepare_next_leg(amr)
                continue
            if amr.assigned_job_id and amr.route_nodes:
                self._advance_amr(amr, dt)
            elif amr.assigned_job_id and not amr.route_nodes:
                self._prepare_next_leg(amr)
            elif amr.route_nodes:
                self._advance_amr(amr, dt)
            elif amr.location != "Loading":
                amr.route_nodes = self._find_path(amr.location, "Loading")
                amr.route_index = 1 if len(amr.route_nodes) > 1 else 0
                amr.status = "Moving"
                amr.current_task = "Returning to loading station"
            elif amr.status != "Idle":
                amr.status = "Idle"
                amr.current_task = "Waiting at loading station"
        self._sync_scheduler_queue()

    def _nearest_location(self, x: float, y: float) -> str:
        return min(STATIONS, key=lambda name: (STATIONS[name][0] - x) ** 2 + (STATIONS[name][1] - y) ** 2)

    def _dispatch_jobs(self) -> None:
        if self.state.system_state != "Running":
            self._sync_scheduler_queue()
            return
        queued_jobs = [job for job in self.state.jobs.values() if job.status == "Queued"]
        queued_jobs.sort(key=lambda item: (-item.priority, item.job_id))
        idle_amrs = [amr for amr in self.state.amrs.values() if amr.assigned_job_id is None]
        idle_amrs.sort(key=lambda item: (self._distance_to_station(item, "Loading"), item.amr_id))
        for job, amr in zip(queued_jobs, idle_amrs):
            self._assign_job(job, amr)
        self._sync_scheduler_queue()

    def _assign_job(self, job: Job, amr: AMRState, manual_override: bool = False) -> None:
        if amr.assigned_job_id and amr.assigned_job_id != job.job_id:
            previous = self.state.jobs.get(amr.assigned_job_id)
            if previous:
                previous.status = "Queued"
                previous.assigned_amr = None
                previous.current_step = 0
        amr.assigned_job_id = job.job_id
        amr.route_nodes = []
        amr.route_index = 0
        job.assigned_amr = amr.amr_id
        job.current_step = 0
        job.status = "Assigned"

        if amr.location != "Loading":
            amr.queued_stations = ["Loading"] + [station for station in job.routing if station != "Loading"]
            job.status = "Returning to Loading"
        else:
            amr.queued_stations = [station for station in job.routing if station != "Loading"]
            job.status = "In Progress"
        amr.status = "Moving"
        amr.current_task = f"Assigned to job {job.job_id}"
        self._prepare_next_leg(amr)
        if manual_override:
            self._sync_scheduler_queue()

    def _prepare_next_leg(self, amr: AMRState) -> None:
        if not amr.assigned_job_id:
            return
        job = self.state.jobs.get(amr.assigned_job_id)
        if not job:
            amr.assigned_job_id = None
            return
        if not amr.queued_stations:
            job.status = "Completed"
            job.current_step = len(job.routing)
            amr.status = "Idle"
            amr.current_task = f"Completed job {job.job_id}"
            amr.assigned_job_id = None
            amr.route_nodes = []
            amr.route_index = 0
            self._add_alert("Info", f"Job {job.job_id} completed by {amr.amr_id}.")
            self._sync_scheduler_queue()
            return

        next_station = amr.queued_stations[0]
        start_node = amr.location if amr.location in PATH_GRAPH else self._nearest_location(amr.x, amr.y)
        station_path = self._find_path(start_node, next_station)
        if not station_path:
            job.status = "Blocked"
            amr.status = "Idle"
            amr.current_task = "No valid path"
            self._add_alert("Warning", f"No path found for job {job.job_id} to {next_station}.")
            return
        amr.route_nodes = station_path
        amr.route_index = 1 if len(station_path) > 1 else 0
        amr.status = "Moving"
        amr.current_task = f"{job.job_id}: moving to {next_station}"
        if next_station == "Loading" and job.status == "Returning to Loading":
            job.current_step = 0
        elif next_station in job.routing:
            job.current_step = job.routing.index(next_station)
            job.status = "In Progress"
        self._sync_scheduler_queue()

    def _advance_amr(self, amr: AMRState, dt: float) -> None:
        if amr.route_index >= len(amr.route_nodes):
            self._prepare_next_leg(amr)
            return
        target_node = amr.route_nodes[amr.route_index]
        target_x, target_y = self._apply_offset(target_node, amr.amr_id)
        distance = hypot(target_x - amr.x, target_y - amr.y)
        step = AMR_SPEED_PX * max(dt, 0.25)
        if distance <= step:
            amr.x = target_x
            amr.y = target_y
            amr.route_index += 1
            if amr.route_index >= len(amr.route_nodes):
                reached_station = amr.route_nodes[-1]
                amr.location = reached_station
                amr.route_nodes = []
                amr.route_index = 0
                if amr.queued_stations and amr.queued_stations[0] == reached_station:
                    amr.queued_stations.pop(0)
                self._on_station_reached(amr, reached_station)
        else:
            ratio = step / distance
            amr.x += (target_x - amr.x) * ratio
            amr.y += (target_y - amr.y) * ratio
            amr.location = self._nearest_location(amr.x, amr.y)
        amr.battery = max(25, amr.battery - 1 if int(time.time()) % 8 == 0 else amr.battery)

    def _on_station_reached(self, amr: AMRState, station: str) -> None:
        if not amr.assigned_job_id:
            amr.status = "Idle"
            amr.current_task = f"Idle at {station}"
            return
        job = self.state.jobs.get(amr.assigned_job_id)
        if not job:
            amr.assigned_job_id = None
            amr.status = "Idle"
            return
        if station == "Loading" and job.status == "Returning to Loading":
            job.status = "In Progress"
            amr.current_task = f"{job.job_id}: picked up material at Loading"
        elif station in job.routing:
            job.current_step = job.routing.index(station)
            if self._station_requires_dwell(station):
                amr.status = "Processing"
                amr.current_task = f"{job.job_id}: processing at {station}"
                amr.dwell_station = station
                amr.dwell_until = time.time() + 2.5
                self._sync_scheduler_queue()
                return
            amr.current_task = f"{job.job_id}: reached {station}"
        self._prepare_next_leg(amr)

    def _find_path(self, start: str, target: str) -> list[str]:
        if start == target:
            return [start]
        queue: deque[list[str]] = deque([[start]])
        visited = {start}
        while queue:
            path = queue.popleft()
            node = path[-1]
            for neighbor in PATH_GRAPH.get(node, []):
                if neighbor in visited:
                    continue
                next_path = path + [neighbor]
                if neighbor == target:
                    return next_path
                visited.add(neighbor)
                queue.append(next_path)
        return []

    def _sync_scheduler_queue(self) -> None:
        self.state.scheduler.queue = [
            {
                "job_id": job.job_id,
                "priority": job.priority,
                "operations": ", ".join(job.operations) if job.operations else "-",
                "next_step": self._next_step_for_job(job),
                "status": job.status,
                "amr": job.assigned_amr or "-",
            }
            for job in sorted(self.state.jobs.values(), key=lambda item: item.job_id)
        ]
        self.state.scheduler.allocations = [
            {
                "amr_id": amr.amr_id,
                "job_id": amr.assigned_job_id or "-",
                "task": amr.current_task,
                "location": amr.location,
            }
            for amr in sorted(self.state.amrs.values(), key=lambda item: item.amr_id)
        ]

    def _next_step_for_job(self, job: Job) -> str:
        if job.status == "Completed":
            return "Completed"
        if job.status == "Returning to Loading":
            return "Loading"
        if job.current_step < len(job.routing):
            return job.routing[job.current_step]
        return "-"

    def _apply_offset(self, node_name: str, amr_id: str) -> tuple[float, float]:
        base_x, base_y = PATH_COORDINATES[node_name]
        if node_name in STATIONS:
            offset_x, offset_y = AMR_DRAW_OFFSETS.get(amr_id, (0, 0))
            return base_x + offset_x, base_y + offset_y
        return base_x, base_y

    def _distance_to_station(self, amr: AMRState, station: str) -> int:
        start_node = amr.location if amr.location in PATH_GRAPH else self._nearest_location(amr.x, amr.y)
        path = self._find_path(start_node, station)
        if not path:
            return 10**9
        return max(len(path) - 1, 0)

    def _station_requires_dwell(self, station: str) -> bool:
        return station.startswith("Machine")

    def _add_alert(self, severity: str, message: str) -> None:
        self.state.alerts.insert(0, AlertEvent(timestamp=datetime.now(), severity=severity, message=message))
        self.state.alerts = self.state.alerts[:12]

    def _calculate_message_rate(self) -> float:
        now = time.time()
        recent = [stamp for stamp in self.message_times if now - stamp <= 60]
        return round(len(recent) / 60, 2)

    def _clone_state(self) -> DashboardState:
        return DashboardState(
            system_state=self.state.system_state,
            active_jobs=self.state.active_jobs,
            job_counter=self.state.job_counter,
            amrs={key: AMRState(**vars(value)) for key, value in self.state.amrs.items()},
            jobs={key: Job(**vars(value)) for key, value in self.state.jobs.items()},
            scheduler=deepcopy(self.state.scheduler),
            alerts=list(self.state.alerts),
            mqtt=deepcopy(self.state.mqtt),
        )
