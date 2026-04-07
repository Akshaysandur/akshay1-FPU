from __future__ import annotations

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from dashboard.config import APP_TITLE, DEFAULT_BASE_TOPIC, DEFAULT_BROKER, DEFAULT_OPERATIONS, DEFAULT_PORT, PROCESS_LABELS, PROCESS_TO_MACHINE
from dashboard.mqtt_client import DashboardMQTTClient
from dashboard.visualization import build_factory_figure


st.set_page_config(page_title=APP_TITLE, layout="wide")


@st.cache_resource
def get_mqtt_client(broker: str, port: int, base_topic: str) -> DashboardMQTTClient:
    client = DashboardMQTTClient(broker=broker, port=port, base_topic=base_topic)
    client.start()
    return client


def status_badge(label: str, value: str, tone: str = "neutral") -> str:
    palette = {
        "good": ("#ebf8ff", "#2b6cb0"),
        "warn": ("#fffaf0", "#c05621"),
        "danger": ("#fff5f5", "#c53030"),
        "neutral": ("#edf2f7", "#2d3748"),
    }
    bg, fg = palette[tone]
    return (
        f"<div style='padding:0.8rem 1rem;border-radius:14px;background:{bg};'>"
        f"<div style='font-size:0.8rem;color:#4a5568;'>{label}</div>"
        f"<div style='font-size:1.25rem;font-weight:700;color:{fg};'>{value}</div>"
        f"</div>"
    )


def route_from_operations(operations: list[str]) -> list[str]:
    route = ["Loading"]
    route.extend(PROCESS_TO_MACHINE[operation] for operation in operations)
    route.append("Unloading")
    return route


def render_sidebar(client: DashboardMQTTClient) -> None:
    st.sidebar.title("Job Control")
    next_job_id = client.get_next_job_id()
    st.sidebar.text_input("Next Job ID", value=next_job_id, disabled=True)

    selected_operations = st.sidebar.multiselect(
        "Select Operations",
        options=list(PROCESS_LABELS.keys()),
        default=DEFAULT_OPERATIONS,
        format_func=lambda item: PROCESS_LABELS[item],
        help="Choose processes and the machine route is generated automatically.",
    )
    route = route_from_operations(selected_operations)
    st.sidebar.text_input("Generated Route", value=" -> ".join(route), disabled=True)
    priority = st.sidebar.slider("Priority", min_value=1, max_value=5, value=3)

    if st.sidebar.button("Create Job", use_container_width=True, disabled=not selected_operations):
        client.publish_job(
            {
                "job_id": next_job_id,
                "routing": route,
                "priority": priority,
                "operations": selected_operations,
            }
        )
        st.rerun()

    st.sidebar.divider()
    if st.sidebar.button("Start System", use_container_width=True):
        client.publish_command("start")
        st.rerun()
    if st.sidebar.button("Stop System", use_container_width=True):
        client.publish_command("stop")
        st.rerun()
    if st.sidebar.button("Reset System", use_container_width=True):
        client.publish_command("reset")
        st.rerun()

    st.sidebar.divider()
    st.sidebar.caption("MQTT Configuration")
    st.sidebar.write(f"Broker: `{client.broker}`")
    st.sidebar.write(f"Port: `{client.port}`")
    st.sidebar.write(f"Topic Root: `{client.base_topic}`")
    st.sidebar.caption("Job numbering starts from 001 and increments only after a job is created.")


def render_top_panels(state) -> None:
    st.subheader("System Overview")
    amr_summary = ", ".join(f"{amr.amr_id}: {amr.status}" for amr in state.amrs.values())
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.markdown(status_badge("System State", state.system_state, "good" if state.system_state == "Running" else "warn"), unsafe_allow_html=True)
    with col2:
        st.markdown(status_badge("Active Jobs", str(state.active_jobs), "neutral"), unsafe_allow_html=True)
    with col3:
        st.markdown(status_badge("AMRs Online", str(len(state.amrs)), "neutral"), unsafe_allow_html=True)
    with col4:
        tone = "good" if state.mqtt.connected else "warn"
        st.markdown(status_badge("MQTT Link", "Connected" if state.mqtt.connected else "Simulation", tone), unsafe_allow_html=True)
    st.caption(amr_summary)


def render_job_tracking(state, client: DashboardMQTTClient) -> None:
    st.subheader("Job Tracking")
    if not state.jobs:
        st.info("No jobs available.")
        return
    job_ids = list(state.jobs.keys())
    selected_job_id = st.selectbox("Select Job", options=job_ids, index=len(job_ids) - 1)
    job = state.jobs[selected_job_id]
    progress_text = f"Step {min(job.current_step + 1, len(job.routing))} of {len(job.routing)}" if job.routing else "No route"
    col1, col2 = st.columns(2)
    with col1:
        st.write(f"**Job ID:** {job.job_id}")
        st.write(f"**Routing:** {' -> '.join(job.routing)}")
        st.write(f"**Operations:** {', '.join(job.operations) if job.operations else '-'}")
        st.write(f"**Status:** {job.status}")
    with col2:
        st.write(f"**Current Step:** {progress_text}")
        st.write(f"**Assigned AMR:** {job.assigned_amr or 'Unassigned'}")
        new_priority = st.number_input("Modify Priority", min_value=1, max_value=5, value=job.priority, key=f"priority_{job.job_id}")
        if st.button("Update Priority", key=f"update_{job.job_id}"):
            client.publish_priority_update(job.job_id, int(new_priority))
            st.rerun()


def render_scheduler(state, client: DashboardMQTTClient) -> None:
    st.subheader("Scheduler Panel")
    left, right, control = st.columns([1.4, 1.4, 1])
    with left:
        st.write(f"Mode: **{state.scheduler.mode}**")
        st.dataframe(pd.DataFrame(state.scheduler.queue or []), use_container_width=True, hide_index=True)
    with right:
        st.write("**AMR Task Allocation**")
        st.dataframe(pd.DataFrame(state.scheduler.allocations or []), use_container_width=True, hide_index=True)
    with control:
        st.write("**Manual Override**")
        amr_id = st.selectbox("AMR for Reassign", options=list(state.amrs.keys()), key="reassign_amr")
        job_options = list(state.jobs.keys()) or ["-"]
        job_id = st.selectbox("Job for Reassign", options=job_options, key="reassign_job")
        if st.button("Reassign Task", use_container_width=True):
            client.publish_reassign(amr_id, job_id)
            st.rerun()


def render_amr_monitoring(state, client: DashboardMQTTClient) -> None:
    st.subheader("AMR Monitoring")
    rows = [
        {
            "AMR": amr.amr_id,
            "Status": amr.status,
            "Battery": f"{amr.battery}%",
            "Task": amr.current_task,
            "Location": amr.location,
            "Assigned Job": amr.assigned_job_id or "-",
        }
        for amr in state.amrs.values()
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    amr_id = st.selectbox("Manual Control AMR", options=list(state.amrs.keys()), key="manual_amr")
    move_col, stop_col = st.columns(2)
    with move_col:
        if st.button("Move", use_container_width=True):
            client.publish_manual_amr(amr_id, "move")
            st.rerun()
    with stop_col:
        if st.button("Stop", use_container_width=True):
            client.publish_manual_amr(amr_id, "stop")
            st.rerun()


def render_alerts(state) -> None:
    st.subheader("Alerts and Events")
    rows = [
        {"Time": alert.timestamp.strftime("%H:%M:%S"), "Severity": alert.severity, "Message": alert.message}
        for alert in state.alerts[:10]
    ]
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_footer(state) -> None:
    st.divider()
    st.caption(
        " | ".join(
            [
                f"Broker: {state.mqtt.broker}:{state.mqtt.port}",
                f"Connection: {'Connected' if state.mqtt.connected else 'Simulation / Offline'}",
                f"Message Rate: {state.mqtt.message_rate} msg/s",
                f"Last Update: {state.mqtt.last_update.strftime('%Y-%m-%d %H:%M:%S') if state.mqtt.last_update else 'N/A'}",
                f"Last Error: {state.mqtt.last_error or 'None'}",
            ]
        )
    )


def main() -> None:
    st.markdown(
        """
        <style>
        .stApp { background: linear-gradient(180deg, #f8fbff 0%, #edf2f7 100%); }
        .block-container { padding-top: 1.2rem; padding-bottom: 1.2rem; }
        [data-testid="stSidebar"] { background: #111827; }
        [data-testid="stSidebar"] * { color: #f9fafb; }
        div[data-testid="stDataFrame"] { background: rgba(255,255,255,0.9); border-radius: 14px; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    st_autorefresh(interval=1000, key="dashboard_refresh")
    st.title(APP_TITLE)
    st.caption("Unified job control, scheduler visibility, and AMR monitoring for fluid production.")

    client = get_mqtt_client(DEFAULT_BROKER, DEFAULT_PORT, DEFAULT_BASE_TOPIC)
    render_sidebar(client)
    state = client.snapshot()

    render_top_panels(state)

    top_left, top_right = st.columns([2.2, 1])
    with top_left:
        st.subheader("Live Factory Visualization")
        st.plotly_chart(build_factory_figure(state.amrs), use_container_width=True, config={"displayModeBar": False})
    with top_right:
        render_job_tracking(state, client)

    render_scheduler(state, client)

    bottom_left, bottom_right = st.columns([1.5, 1])
    with bottom_left:
        render_amr_monitoring(state, client)
    with bottom_right:
        render_alerts(state)

    render_footer(state)


if __name__ == "__main__":
    main()
