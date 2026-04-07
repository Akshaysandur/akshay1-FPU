from __future__ import annotations

import os
from pathlib import Path


APP_TITLE = "Fluid Production System Dashboard"
DEFAULT_BROKER = os.getenv("MQTT_BROKER_HOST", "broker.hivemq.com")
DEFAULT_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
DEFAULT_BASE_TOPIC = os.getenv("MQTT_BASE_TOPIC", "fluid/fps")
LAYOUT_IMAGE = Path(__file__).resolve().parents[1] / "layout.png"

STATIONS = {
    "Loading": (78, 185),
    "Machine1": (275, 175),
    "Machine2": (205, 390),
    "Machine3": (285, 390),
    "Machine4": (470, 175),
    "Unloading": (533, 270),
    "Charging": (504, 425),
}

PATH_GRAPH = {
    "Loading": ["LoadingJoin"],
    "LoadingJoin": ["Loading", "TopLeft", "BottomLeft"],
    "TopLeft": ["LoadingJoin", "Machine1Join"],
    "Machine1Join": ["TopLeft", "Machine1", "TopMiddle"],
    "Machine1": ["Machine1Join"],
    "TopMiddle": ["Machine1Join", "Machine4Join", "CenterLane"],
    "Machine4Join": ["TopMiddle", "Machine4", "UnloadJoin"],
    "Machine4": ["Machine4Join"],
    "BottomLeft": ["LoadingJoin", "Machine2Join", "Machine3Join"],
    "Machine2Join": ["BottomLeft", "Machine2", "CenterLane"],
    "Machine2": ["Machine2Join"],
    "UnloadJoin": ["Machine4Join", "Unloading", "CenterLane", "ChargingJoin"],
    "Unloading": ["UnloadJoin"],
    "CenterLane": ["TopMiddle", "UnloadJoin", "Machine2Join", "Machine3Join", "ChargingJoin"],
    "Machine3Join": ["CenterLane", "Machine3", "BottomLeft"],
    "Machine3": ["Machine3Join"],
    "ChargingJoin": ["CenterLane", "UnloadJoin", "Charging"],
    "Charging": ["ChargingJoin"],
}

PATH_COORDINATES = {
    "Loading": STATIONS["Loading"],
    "LoadingJoin": (150, 208),
    "TopLeft": (225, 208),
    "Machine1Join": (275, 208),
    "Machine1": STATIONS["Machine1"],
    "TopMiddle": (365, 208),
    "Machine4Join": (470, 208),
    "Machine4": STATIONS["Machine4"],
    "BottomLeft": (160, 365),
    "Machine2Join": (205, 365),
    "Machine2": STATIONS["Machine2"],
    "UnloadJoin": (515, 270),
    "Unloading": STATIONS["Unloading"],
    "CenterLane": (350, 300),
    "Machine3Join": (285, 365),
    "Machine3": STATIONS["Machine3"],
    "ChargingJoin": (470, 390),
    "Charging": STATIONS["Charging"],
}

AMR_DRAW_OFFSETS = {
    "AMR-01": (-10, -8),
    "AMR-02": (10, -4),
    "AMR-03": (0, 10),
}

AMR_SPEED_PX = 60.0

PROCESS_TO_MACHINE = {
    "Painting": "Machine1",
    "Assembly": "Machine2",
    "Inspection": "Machine3",
    "Welding": "Machine4",
}

PROCESS_LABELS = {
    "Painting": "Painting (Machine 1)",
    "Assembly": "Assembly (Machine 2)",
    "Inspection": "Inspection (Machine 3)",
    "Welding": "Welding (Machine 4)",
}

DEFAULT_OPERATIONS: list[str] = []
