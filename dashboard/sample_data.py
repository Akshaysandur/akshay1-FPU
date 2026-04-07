from __future__ import annotations

from datetime import datetime

from dashboard.config import AMR_DRAW_OFFSETS, DEFAULT_OPERATIONS, PROCESS_TO_MACHINE, STATIONS
from dashboard.models import AMRState, AlertEvent, DashboardState


def _loading_position(amr_id: str) -> tuple[float, float]:
    base_x, base_y = STATIONS["Loading"]
    offset_x, offset_y = AMR_DRAW_OFFSETS[amr_id]
    return base_x + offset_x, base_y + offset_y


def build_initial_state() -> DashboardState:
    state = DashboardState()
    state.job_counter = 0
    state.amrs = {
        "AMR-01": AMRState(
            amr_id="AMR-01",
            status="Idle",
            battery=92,
            current_task="Waiting at loading station",
            location="Loading",
            x=_loading_position("AMR-01")[0],
            y=_loading_position("AMR-01")[1],
        ),
        "AMR-02": AMRState(
            amr_id="AMR-02",
            status="Idle",
            battery=88,
            current_task="Waiting at loading station",
            location="Loading",
            x=_loading_position("AMR-02")[0],
            y=_loading_position("AMR-02")[1],
        ),
        "AMR-03": AMRState(
            amr_id="AMR-03",
            status="Idle",
            battery=84,
            current_task="Waiting at loading station",
            location="Loading",
            x=_loading_position("AMR-03")[0],
            y=_loading_position("AMR-03")[1],
        ),
    }
    state.active_jobs = 0
    state.system_state = "Running"
    state.scheduler.mode = "Dynamic"
    state.scheduler.queue = []
    state.scheduler.allocations = []
    state.alerts = [
        AlertEvent(timestamp=datetime.now(), severity="Info", message="Dashboard initialized with all AMRs at the loading station."),
        AlertEvent(
            timestamp=datetime.now(),
            severity="Info",
            message="Select operations such as "
            + ", ".join(f"{name}->{PROCESS_TO_MACHINE[name]}" for name in DEFAULT_OPERATIONS)
            + " or Welding->Machine4 to generate the route automatically.",
        ),
    ]
    return state
