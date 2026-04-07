from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass
class Job:
    job_id: str
    routing: list[str]
    priority: int
    operations: list[str] = field(default_factory=list)
    current_step: int = 0
    status: str = "Queued"
    assigned_amr: str | None = None


@dataclass
class AMRState:
    amr_id: str
    status: str = "Idle"
    battery: int = 100
    current_task: str = "Awaiting assignment"
    location: str = "Loading"
    x: float = 0.0
    y: float = 0.0
    assigned_job_id: str | None = None
    route_nodes: list[str] = field(default_factory=list)
    route_index: int = 0
    queued_stations: list[str] = field(default_factory=list)


@dataclass
class SchedulerState:
    mode: str = "Dynamic"
    queue: list[dict[str, Any]] = field(default_factory=list)
    allocations: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class AlertEvent:
    timestamp: datetime
    severity: str
    message: str


@dataclass
class MQTTStatus:
    connected: bool = False
    broker: str = "localhost"
    port: int = 1883
    message_rate: float = 0.0
    last_update: datetime | None = None
    last_error: str = ""


@dataclass
class DashboardState:
    system_state: str = "Stopped"
    active_jobs: int = 0
    job_counter: int = 0
    amrs: dict[str, AMRState] = field(default_factory=dict)
    jobs: dict[str, Job] = field(default_factory=dict)
    scheduler: SchedulerState = field(default_factory=SchedulerState)
    alerts: list[AlertEvent] = field(default_factory=list)
    mqtt: MQTTStatus = field(default_factory=MQTTStatus)
