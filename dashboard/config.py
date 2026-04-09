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
    "Loading": ["LoadingTop", "LoadingDown"],
    "LoadingTop": ["Loading", "TopWest"],
    "TopWest": ["LoadingTop", "Machine1Entry"],
    "Machine1Entry": ["TopWest", "Machine1", "TopCenter"],
    "Machine1": ["Machine1Entry"],
    "TopCenter": ["Machine1Entry", "Machine4Entry", "Machine3Drop"],
    "Machine4Entry": ["TopCenter", "Machine4", "TopRightDrop"],
    "Machine4": ["Machine4Entry"],
    "TopRightDrop": ["Machine4Entry", "SpineRight"],
    "LoadingDown": ["Loading", "SpineWest"],
    "SpineWest": ["LoadingDown", "Machine2Drop"],
    "Machine2Drop": ["SpineWest", "Machine2Entry"],
    "Machine2Entry": ["Machine2Drop", "Machine2", "BottomCross"],
    "Machine2": ["Machine2Entry"],
    "BottomCross": ["Machine2Entry", "Machine3Entry"],
    "Machine3Entry": ["BottomCross", "Machine3", "Machine3Drop"],
    "Machine3": ["Machine3Entry"],
    "Machine3Drop": ["Machine3Entry", "TopCenter", "SpineCenter"],
    "SpineCenter": ["Machine3Drop", "SpineRight"],
    "SpineRight": ["SpineCenter", "TopRightDrop", "UnloadJoin", "ChargeTurn"],
    "UnloadJoin": ["SpineRight", "Unloading"],
    "Unloading": ["UnloadJoin"],
    "ChargeTurn": ["SpineRight", "Charging"],
    "Charging": ["ChargeTurn"],
}

PATH_COORDINATES = {
    "Loading": STATIONS["Loading"],
    "LoadingTop": (78, 125),
    "TopWest": (170, 125),
    "Machine1Entry": (170, 175),
    "Machine1": STATIONS["Machine1"],
    "TopCenter": (360, 175),
    "Machine4Entry": (455, 175),
    "Machine4": STATIONS["Machine4"],
    "TopRightDrop": (470, 285),
    "LoadingDown": (95, 285),
    "SpineWest": (205, 285),
    "SpineCenter": (360, 285),
    "SpineRight": (490, 285),
    "UnloadJoin": (532, 285),
    "Unloading": STATIONS["Unloading"],
    "ChargeTurn": (490, 375),
    "Charging": STATIONS["Charging"],
    "Machine2Drop": (205, 345),
    "Machine2Entry": (205, 390),
    "Machine2": STATIONS["Machine2"],
    "BottomCross": (255, 390),
    "Machine3Entry": (285, 390),
    "Machine3": STATIONS["Machine3"],
    "Machine3Drop": (355, 390),
}

PATH_OVERLAY = [
    ["Loading", "LoadingTop", "TopWest", "Machine1Entry", "TopCenter", "Machine4Entry", "TopRightDrop", "SpineRight"],
    ["Loading", "LoadingDown", "SpineWest", "Machine2Drop", "Machine2Entry", "Machine2", "BottomCross", "Machine3Entry", "Machine3", "Machine3Drop", "SpineCenter", "SpineRight"],
    ["SpineRight", "UnloadJoin", "Unloading"],
    ["SpineRight", "ChargeTurn", "Charging"],
]

AMR_DRAW_OFFSETS = {
    "AMR-01": (-10, -8),
    "AMR-02": (10, -4),
    "AMR-03": (0, 10),
    "AMR-04": (18, 12),
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
