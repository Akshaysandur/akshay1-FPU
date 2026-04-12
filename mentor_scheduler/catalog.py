from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OperationTemplate:
    name: str
    machine: str
    minutes: int
    description: str = ""


OPERATION_CATALOG: dict[str, OperationTemplate] = {
    "Drilling": OperationTemplate("Drilling", "Machine 1", 8, "Basic drilling"),
    "Turning": OperationTemplate("Turning", "Machine 2", 7, "Lathe turning"),
    "Assembly": OperationTemplate("Assembly", "Machine 3", 10, "Manual assembly"),
    "Inspection": OperationTemplate("Inspection", "Machine 4", 6, "Quality inspection"),
    "Welding": OperationTemplate("Welding", "Machine 5", 12, "Welding and joining"),
}

FMS_INFO = {
    "Scheduler": "Static / Dynamic",
    "Loading": "Zero time",
    "Unloading": "Zero time",
    "Execution": "Step-by-step order progress",
}
