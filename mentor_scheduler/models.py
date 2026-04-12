from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class OperationStep:
    name: str
    machine: str
    minutes: int
    status: str = "Pending"


@dataclass
class JobOrder:
    order_id: str
    customer: str
    item_name: str
    priority: int
    created_at: datetime
    due_date: str = ""
    notes: str = ""
    status: str = "Queued"
    current_step_index: int = 0
    queue_seconds_remaining: int = 0
    operations: list[OperationStep] = field(default_factory=list)

    def route_labels(self) -> list[str]:
        labels = ["Loading"]
        labels.extend(f"{step.name} ({step.machine}, {step.minutes} min)" for step in self.operations)
        labels.append("Unloading")
        return labels

    def tree_text(self) -> str:
        lines = [f"Order {self.order_id}"]
        lines.append("  Loading")
        for index, step in enumerate(self.operations, start=1):
            lines.append(f"  {index}. {step.name} -> {step.machine} ({step.minutes} min)")
        lines.append("  Unloading")
        return "\n".join(lines)


@dataclass
class SchedulerState:
    mode: str = "Dynamic"
    last_run: datetime | None = None
    active_order_id: str = ""
