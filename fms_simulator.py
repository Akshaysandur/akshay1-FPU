from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

try:
    import paho.mqtt.client as mqtt
except ImportError as exc:  # pragma: no cover
    raise SystemExit("Install dependencies with: pip install -r fms_requirements.txt") from exc


IST = ZoneInfo("Asia/Kolkata")

TOPICS = {
    "jobs_create": "fluid/fpu/jobs/create",
    "system_start": "fluid/fpu/system/start",
    "system_stop": "fluid/fpu/system/stop",
    "system_reset": "fluid/fpu/system/reset",
    "scheduler_reassign": "fluid/fpu/scheduler/reassign",
    "job_priority": "fluid/fpu/jobs/priority",
    "amr_manual": "fluid/fpu/amr/manual",
    "status_system": "fluid/fpu/status/system",
    "status_amr": "fluid/fpu/status/amr",
    "scheduler_queue": "fluid/fpu/scheduler/queue",
    "alerts_event": "fluid/fpu/alerts/event",
}


@dataclass
class Operation:
    name: str
    machine: str
    minutes: int
    status: str = "Pending"


@dataclass
class Order:
    order_id: str
    customer: str
    item_name: str
    priority: int
    due_date: str
    notes: str
    created_at: datetime
    status: str = "Queued"
    current_step_index: int = 0
    queue_seconds_remaining: int = 0
    operations: list[Operation] = field(default_factory=list)


OPERATION_CATALOG = {
    "Drilling": ("Machine 1", 8),
    "Turning": ("Machine 2", 7),
    "Assembly": ("Machine 3", 10),
    "Inspection": ("Machine 4", 6),
    "Welding": ("Machine 5", 12),
}


class FmsSimulator:
    def __init__(self, broker_host: str, broker_port: int) -> None:
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.system_state = "Stopped"
        self.orders: dict[str, Order] = {}
        self.lock = threading.Lock()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"fms_{os.getpid()}")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def connect(self) -> None:
        self.client.connect(self.broker_host, self.broker_port, keepalive=60)
        self.client.loop_start()
        threading.Thread(target=self.tick_loop, daemon=True).start()
        print(f"Connected to MQTT broker {self.broker_host}:{self.broker_port}")

    def on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        print(f"MQTT connected: {reason_code}")
        client.subscribe([(TOPICS["jobs_create"], 0), (TOPICS["system_start"], 0), (TOPICS["system_stop"], 0),
                          (TOPICS["system_reset"], 0), (TOPICS["scheduler_reassign"], 0),
                          (TOPICS["job_priority"], 0), (TOPICS["amr_manual"], 0)])
        self.publish_snapshots("FMS online")

    def on_message(self, client, userdata, msg) -> None:
        payload = msg.payload.decode("utf-8", errors="ignore")
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            data = payload

        if msg.topic == TOPICS["jobs_create"] and isinstance(data, dict):
            self.handle_job_create(data)
        elif msg.topic == TOPICS["system_start"]:
            self.system_state = "Running"
            self.publish_system("System running.")
        elif msg.topic == TOPICS["system_stop"]:
            self.system_state = "Stopped"
            self.publish_system("System stopped.")
        elif msg.topic == TOPICS["system_reset"]:
            with self.lock:
                self.orders.clear()
                self.system_state = "Stopped"
            self.publish_snapshots("System reset.")
        elif msg.topic == TOPICS["scheduler_reassign"]:
            self.publish_queue("Reassign requested.")
        elif msg.topic == TOPICS["job_priority"]:
            self.publish_queue("Priority updated.")
        elif msg.topic == TOPICS["amr_manual"]:
            self.publish_amrs("Manual AMR command received.")

    def handle_job_create(self, data: dict) -> None:
        order_id = str(data.get("orderId") or data.get("order_id") or "").strip()
        if not order_id:
            return
        operations = [
            Operation(name=op.get("name", ""), machine=op.get("machine", ""), minutes=int(op.get("minutes", 0)))
            for op in data.get("operations", [])
            if isinstance(op, dict)
        ]
        with self.lock:
            self.orders[order_id] = Order(
                order_id=order_id,
                customer=str(data.get("customer", "")),
                item_name=str(data.get("itemName") or data.get("item_name") or ""),
                priority=int(data.get("priority", 3)),
                due_date=str(data.get("dueDate") or data.get("due_date") or ""),
                notes=str(data.get("notes", "")),
                created_at=datetime.now(IST),
                operations=operations,
            )
        self.publish_system(f"Job {order_id} stored.")
        self.publish_queue(f"Job {order_id} queued.")
        self.publish_amrs(f"AMR assignment ready for {order_id}.")
        self.publish_alert("Info", f"Job {order_id} created.")

    def publish_json(self, topic: str, payload: dict) -> None:
        self.client.publish(topic, json.dumps(payload), qos=0, retain=False)

    def publish_system(self, message: str) -> None:
        self.publish_json(
            TOPICS["status_system"],
            {
                "message": message,
                "systemState": self.system_state,
                "activeJobs": self.active_jobs(),
                "updatedAt": datetime.now(IST).isoformat(),
            },
        )

    def publish_amrs(self, message: str) -> None:
        self.publish_json(
            TOPICS["status_amr"],
            {
                "message": message,
                "amrs": [
                    {"amrId": "AMR-01", "status": "Idle", "battery": 88, "task": "Awaiting dispatch", "location": "Loading"},
                    {"amrId": "AMR-02", "status": "Charging", "battery": 48, "task": "Charging cycle", "location": "Charging"},
                    {"amrId": "AMR-03", "status": "Idle", "battery": 76, "task": "Awaiting dispatch", "location": "Loading"},
                    {"amrId": "AMR-04", "status": "Idle", "battery": 92, "task": "Awaiting dispatch", "location": "Loading"},
                ],
                "updatedAt": datetime.now(IST).isoformat(),
            },
        )

    def publish_queue(self, message: str) -> None:
        with self.lock:
            queue = [self.order_summary(order) for order in self.sorted_orders()]
        self.publish_json(
            TOPICS["scheduler_queue"],
            {"message": message, "mode": "Dynamic", "queue": queue, "updatedAt": datetime.now(IST).isoformat()},
        )

    def publish_alert(self, severity: str, message: str) -> None:
        self.publish_json(
            TOPICS["alerts_event"],
            {"severity": severity, "message": message, "timestamp": datetime.now(IST).isoformat()},
        )

    def publish_snapshots(self, message: str) -> None:
        self.publish_system(message)
        self.publish_queue(message)
        self.publish_amrs(message)

    def active_jobs(self) -> int:
        return len([order for order in self.orders.values() if order.status not in {"Completed", "Cancelled"}])

    def sorted_orders(self) -> list[Order]:
        return sorted(self.orders.values(), key=lambda order: (-order.priority, order.created_at, order.order_id))

    def order_summary(self, order: Order) -> dict[str, object]:
        next_step = "Unloading" if order.current_step_index >= len(order.operations) else f"{order.operations[order.current_step_index].name} / {order.operations[order.current_step_index].machine}"
        return {
            "Order ID": order.order_id,
            "Customer": order.customer,
            "Item": order.item_name,
            "Priority": order.priority,
            "Ops": len(order.operations),
            "Status": order.status,
            "Next Step": next_step,
            "Queue Time": f"{order.queue_seconds_remaining}s",
        }

    def tick_loop(self) -> None:
        while True:
            time.sleep(1)
            changed = False
            with self.lock:
                ordered = self.sorted_orders()
                running_active = any(order.status == "Running" for order in ordered)
                for order in ordered:
                    if order.status == "Queued" and not running_active:
                        order.status = "Running"
                        order.queue_seconds_remaining = max(2, len(order.operations))
                        running_active = True
                        changed = True
                    elif order.status == "Running":
                        if order.queue_seconds_remaining > 0:
                            order.queue_seconds_remaining -= 1
                            changed = True
                        elif order.current_step_index < len(order.operations):
                            self.advance(order)
                            changed = True
                        else:
                            order.status = "Completed"
                            changed = True
                    elif order.status == "Unloading":
                        if order.queue_seconds_remaining > 0:
                            order.queue_seconds_remaining -= 1
                            changed = True
                        else:
                            order.status = "Completed"
                            order.current_step_index = len(order.operations)
                            changed = True
            if changed:
                self.publish_snapshots("Live queue update.")

    def advance(self, order: Order) -> None:
        if order.current_step_index < len(order.operations):
            order.operations[order.current_step_index].status = "Done"
            order.current_step_index += 1
            if order.current_step_index < len(order.operations):
                order.status = "Running"
            else:
                order.status = "Unloading"
                order.queue_seconds_remaining = 2


def main() -> None:
    broker_host = os.environ.get("FMS_BROKER_HOST", "broker.hivemq.com")
    broker_port = int(os.environ.get("FMS_BROKER_PORT", "1883"))
    simulator = FmsSimulator(broker_host, broker_port)
    simulator.connect()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("Stopping FMS simulator...")
        simulator.client.loop_stop()
        simulator.client.disconnect()


if __name__ == "__main__":
    main()
