from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from mentor_scheduler.catalog import FMS_INFO, OPERATION_CATALOG
from mentor_scheduler.models import DraftOperation, JobOrder
from mentor_scheduler.scheduler import advance_order, build_order, complete_order, next_step, queue_summary, sort_orders, tick_scheduler


st.set_page_config(page_title="FPU Job Scheduler", layout="wide")


def utc_today_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def first_operation_name() -> str:
    return next(iter(OPERATION_CATALOG))


def sync_order_id() -> None:
    st.session_state.order_id_field = f"ORD-{st.session_state.next_order_no:03d}"


def sync_operation_defaults() -> None:
    first_name = first_operation_name()
    st.session_state.operation_picker = first_name
    st.session_state.operation_last_name = first_name
    st.session_state.operation_minutes = OPERATION_CATALOG[first_name].minutes


def reset_metadata(clear_metadata: bool) -> None:
    if clear_metadata:
        st.session_state.customer_field = ""
        st.session_state.item_name_field = ""
        st.session_state.due_date_field = utc_today_str()
        st.session_state.notes_field = ""
        st.session_state.priority_field = 3
    st.session_state.draft_ops = []
    st.session_state.order_locked = False
    sync_operation_defaults()


def next_execution_focus(orders: list[JobOrder], mode: str, current_id: str = "") -> str:
    active = [order for order in sort_orders(orders, mode) if order.status not in {"Completed", "Cancelled"}]
    if not active:
        return ""
    active_ids = [order.order_id for order in active]
    if current_id in active_ids:
        current_index = active_ids.index(current_id)
        if current_index + 1 < len(active_ids):
            return active_ids[current_index + 1]
        if current_index > 0:
            return active_ids[current_index - 1]
    return active_ids[0]


def init_state() -> None:
    if "orders" not in st.session_state:
        st.session_state.orders: list[JobOrder] = []
    if "draft_ops" not in st.session_state:
        st.session_state.draft_ops: list[DraftOperation] = []
    if "scheduler_mode" not in st.session_state:
        st.session_state.scheduler_mode = "Dynamic"
    if "selected_order" not in st.session_state:
        st.session_state.selected_order = ""
    if "execution_focus_order" not in st.session_state:
        st.session_state.execution_focus_order = ""
    if "next_order_no" not in st.session_state:
        st.session_state.next_order_no = 1
    if "order_locked" not in st.session_state:
        st.session_state.order_locked = False
    if "order_id_field" not in st.session_state:
        st.session_state.order_id_field = f"ORD-{st.session_state.next_order_no:03d}"
    if "customer_field" not in st.session_state:
        st.session_state.customer_field = ""
    if "item_name_field" not in st.session_state:
        st.session_state.item_name_field = ""
    if "due_date_field" not in st.session_state:
        st.session_state.due_date_field = utc_today_str()
    if "notes_field" not in st.session_state:
        st.session_state.notes_field = ""
    if "priority_field" not in st.session_state:
        st.session_state.priority_field = 3
    if "operation_picker" not in st.session_state:
        sync_operation_defaults()
    if "operation_minutes" not in st.session_state:
        st.session_state.operation_minutes = OPERATION_CATALOG[st.session_state.operation_picker].minutes
    if "operation_last_name" not in st.session_state:
        st.session_state.operation_last_name = st.session_state.operation_picker
    sync_order_id()


def app_style() -> None:
    st.markdown(
        """
        <style>
        @keyframes floatGlow {
            0% { transform: translate3d(0, 0, 0) scale(1); opacity: 0.72; }
            50% { transform: translate3d(0, -8px, 0) scale(1.03); opacity: 1; }
            100% { transform: translate3d(0, 0, 0) scale(1); opacity: 0.72; }
        }
        @keyframes shimmer {
            0% { background-position: 0% 50%; }
            100% { background-position: 100% 50%; }
        }
        @keyframes riseIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(250, 204, 21, 0.18), transparent 20%),
                radial-gradient(circle at 90% 10%, rgba(59, 130, 246, 0.18), transparent 18%),
                radial-gradient(circle at bottom right, rgba(244, 114, 182, 0.12), transparent 24%),
                linear-gradient(180deg, #040614 0%, #09111f 50%, #0f172a 100%);
            color: #f8fafc;
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #020617 0%, #0f172a 100%);
            border-right: 1px solid rgba(148, 163, 184, 0.12);
        }
        [data-testid="stSidebar"] * {
            color: #f8fafc;
        }
        [data-baseweb="tab-list"] {
            gap: 0.4rem;
            padding: 0.55rem 0.65rem;
            border-radius: 16px;
            border: 1px solid rgba(148, 163, 184, 0.12);
            background: linear-gradient(90deg, rgba(15, 23, 42, 0.85), rgba(30, 41, 59, 0.82));
            box-shadow: 0 18px 34px rgba(2, 6, 23, 0.28);
        }
        [data-baseweb="tab"] {
            background: linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.01));
            border-radius: 12px 12px 0 0;
            color: #dbeafe;
            font-weight: 700;
            padding: 0.5rem 0.9rem;
            transition: transform 180ms ease, background 180ms ease, color 180ms ease;
        }
        [data-baseweb="tab"]:hover {
            transform: translateY(-1px);
            color: #fff7cc;
        }
        [data-baseweb="tab"][aria-selected="true"] {
            background: linear-gradient(180deg, rgba(250,204,21,0.28), rgba(59,130,246,0.18));
            color: #ffffff;
            border-bottom: 2px solid #facc15;
        }
        .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
        }
        .hero-shell {
            position: relative;
            overflow: hidden;
            border-radius: 24px;
            padding: 1.15rem 1.35rem;
            margin: 0.25rem 0 1rem;
            border: 1px solid rgba(250, 204, 21, 0.18);
            background:
                linear-gradient(135deg, rgba(15, 23, 42, 0.96), rgba(30, 41, 59, 0.82)),
                radial-gradient(circle at top left, rgba(250, 204, 21, 0.14), transparent 30%);
            box-shadow: 0 18px 40px rgba(2, 6, 23, 0.3);
            animation: riseIn 420ms ease;
        }
        .hero-shell::before,
        .hero-shell::after {
            content: "";
            position: absolute;
            border-radius: 999px;
            filter: blur(4px);
            pointer-events: none;
        }
        .hero-shell::before {
            width: 220px;
            height: 220px;
            right: -70px;
            top: -80px;
            background: radial-gradient(circle, rgba(250,204,21,0.35), transparent 68%);
            animation: floatGlow 6s ease-in-out infinite;
        }
        .hero-shell::after {
            width: 180px;
            height: 180px;
            left: 42%;
            bottom: -100px;
            background: radial-gradient(circle, rgba(59,130,246,0.25), transparent 68%);
            animation: floatGlow 7s ease-in-out infinite reverse;
        }
        .hero-kicker {
            display: inline-block;
            padding: 0.25rem 0.7rem;
            border-radius: 999px;
            background: linear-gradient(90deg, #facc15, #fb7185);
            color: #09111f;
            font-weight: 800;
            letter-spacing: 0.04em;
            font-size: 0.74rem;
            text-transform: uppercase;
        }
        .hero-title {
            font-size: clamp(2rem, 3vw, 3rem);
            line-height: 1.05;
            font-weight: 900;
            margin-top: 0.65rem;
            margin-bottom: 0.45rem;
            background: linear-gradient(90deg, #ffffff, #fde68a, #93c5fd);
            -webkit-background-clip: text;
            background-clip: text;
            color: transparent;
            animation: shimmer 10s linear infinite alternate;
            background-size: 200% 200%;
        }
        .hero-subtitle {
            max-width: 64ch;
            color: #cbd5e1;
            font-size: 0.98rem;
            margin-bottom: 0.9rem;
        }
        .hero-pills {
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
        }
        .hero-pill {
            padding: 0.38rem 0.75rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.08);
            color: #f8fafc;
            font-size: 0.83rem;
        }
        .stat-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 0.8rem;
            margin-bottom: 1rem;
        }
        .stat-card {
            border-radius: 18px;
            padding: 0.9rem 1rem;
            border: 1px solid rgba(255,255,255,0.12);
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.9), rgba(30, 41, 59, 0.9));
            box-shadow: 0 14px 28px rgba(2, 6, 23, 0.22);
            animation: riseIn 420ms ease;
            transition: transform 180ms ease, box-shadow 180ms ease;
        }
        .stat-card:hover {
            transform: translateY(-3px);
            box-shadow: 0 20px 36px rgba(2, 6, 23, 0.34);
        }
        .stat-accent-yellow {
            border-color: rgba(250,204,21,0.35);
            box-shadow: inset 0 0 0 1px rgba(250,204,21,0.08), 0 14px 28px rgba(250,204,21,0.06);
        }
        .stat-accent-blue {
            border-color: rgba(59,130,246,0.35);
        }
        .stat-accent-pink {
            border-color: rgba(244,114,182,0.3);
        }
        .stat-label {
            color: #cbd5e1;
            font-size: 0.78rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.35rem;
        }
        .stat-value {
            font-size: 1.5rem;
            font-weight: 900;
            color: #ffffff;
        }
        .stat-foot {
            color: #94a3b8;
            font-size: 0.82rem;
            margin-top: 0.2rem;
        }
        .panel-card {
            background: rgba(15, 23, 42, 0.82);
            border: 1px solid rgba(148, 163, 184, 0.16);
            border-radius: 18px;
            padding: 1rem 1.1rem;
            box-shadow: 0 18px 36px rgba(2, 6, 23, 0.25);
            animation: riseIn 360ms ease;
        }
        .fpu-muted {
            color: #aeb9ca;
            font-size: 0.92rem;
        }
        .fpu-route {
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
            line-height: 1.6;
            white-space: pre-wrap;
            color: #e5eefb;
        }
        h1, h2, h3, h4, p, label, span, div { color: #e5eefb; }
        .stDataFrame, [data-testid="stDataFrame"] {
            background: rgba(15, 23, 42, 0.8);
            border-radius: 14px;
        }
        div[data-testid="stButton"] button {
            border: 1px solid rgba(250, 204, 21, 0.28);
            border-radius: 14px;
            background: linear-gradient(135deg, rgba(250, 204, 21, 0.98), rgba(251, 146, 60, 0.92));
            color: #09111f;
            font-weight: 900;
            box-shadow: 0 10px 20px rgba(250, 204, 21, 0.2);
            transition: transform 180ms ease, box-shadow 180ms ease, filter 180ms ease;
        }
        div[data-testid="stButton"] button:hover {
            transform: translateY(-2px);
            filter: brightness(1.06);
            box-shadow: 0 14px 26px rgba(250, 204, 21, 0.28);
        }
        div[data-testid="stButton"] button[kind="secondary"] {
            background: linear-gradient(135deg, rgba(30, 41, 59, 0.96), rgba(15, 23, 42, 0.96));
            color: #f8fafc;
            border: 1px solid rgba(148, 163, 184, 0.18);
            box-shadow: none;
        }
        div[data-testid="stTextInput"] input,
        div[data-testid="stTextArea"] textarea,
        div[data-baseweb="select"] > div,
        div[data-baseweb="input"] > div,
        div[data-testid="stNumberInput"] input {
            background-color: rgba(15, 23, 42, 0.92) !important;
            color: #f8fafc !important;
            border-color: rgba(148, 163, 184, 0.18) !important;
            border-radius: 14px !important;
        }
        div[data-baseweb="select"] > div:hover,
        div[data-testid="stTextInput"] input:focus,
        div[data-testid="stTextArea"] textarea:focus,
        div[data-testid="stNumberInput"] input:focus {
            border-color: rgba(250, 204, 21, 0.55) !important;
            box-shadow: 0 0 0 1px rgba(250, 204, 21, 0.2) !important;
        }
        [data-testid="stHorizontalBlock"] > div > div {
            gap: 0.75rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def header() -> None:
    st.markdown(
        """
        <div class="hero-shell">
            <div class="hero-kicker">FPU Job Scheduler</div>
            <div class="hero-title">Bright, tactile, and built for fast job control.</div>
            <div class="hero-subtitle">
                Manage orders, tune operation times, and watch the queue progress with a more colorful control-room feel.
            </div>
            <div class="hero-pills">
                <span class="hero-pill">Live queue</span>
                <span class="hero-pill">Editable operation times</span>
                <span class="hero-pill">Step execution</span>
                <span class="hero-pill">Dark neon workflow</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_summary_strip() -> None:
    total_orders = len(st.session_state.orders)
    active_orders = len([order for order in st.session_state.orders if order.status not in {"Completed", "Cancelled"}])
    focus_order = st.session_state.execution_focus_order or st.session_state.selected_order or "None"
    utc_stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    st.markdown(
        f"""
        <div class="stat-grid">
            <div class="stat-card stat-accent-yellow">
                <div class="stat-label">Orders</div>
                <div class="stat-value">{total_orders}</div>
                <div class="stat-foot">Created in this session</div>
            </div>
            <div class="stat-card stat-accent-blue">
                <div class="stat-label">Active Jobs</div>
                <div class="stat-value">{active_orders}</div>
                <div class="stat-foot">Waiting or running now</div>
            </div>
            <div class="stat-card stat-accent-pink">
                <div class="stat-label">Focused Job</div>
                <div class="stat-value">{focus_order}</div>
                <div class="stat-foot">Execution tab selection</div>
            </div>
            <div class="stat-card">
                <div class="stat-label">UTC Clock</div>
                <div class="stat-value" style="font-size:1.05rem;">{utc_stamp}</div>
                <div class="stat-foot">Auto-filled due date source</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def sidebar_controls() -> None:
    st.sidebar.header("FPU Basics")
    st.sidebar.write(f"Scheduler mode: **{st.session_state.scheduler_mode}**")
    st.sidebar.write(f"Next order: **{st.session_state.order_id_field}**")
    st.sidebar.write(f"UTC date: **{utc_today_str()}**")
    st.sidebar.divider()
    st.sidebar.caption("Simple scheduler for job metadata, draft building, and execution flow.")


def render_order_builder() -> None:
    st.subheader("Add Order")
    left, right = st.columns([1.1, 0.9], gap="large")

    with left:
        with st.container(border=True):
            st.markdown("**Job Metadata**")
            col1, col2 = st.columns(2)
            metadata_locked = st.session_state.order_locked
            with col1:
                st.text_input("Order ID", key="order_id_field", disabled=True)
                st.text_input("Customer", placeholder="Customer name", key="customer_field", disabled=metadata_locked)
                st.slider("Priority", 1, 5, key="priority_field", disabled=metadata_locked)
            with col2:
                st.text_input("Item / Job Name", placeholder="Part or product name", key="item_name_field", disabled=metadata_locked)
                st.text_input("Due Date", key="due_date_field", disabled=True)
                st.text_area("Notes", placeholder="Optional notes", height=110, key="notes_field", disabled=metadata_locked)

            st.markdown("**Operation Builder**")
            op_col, machine_col, time_col = st.columns([1.25, 1, 0.75])
            operation_names = list(OPERATION_CATALOG.keys())
            with op_col:
                current_operation = st.selectbox(
                    "Operation",
                    options=operation_names,
                    index=operation_names.index(st.session_state.operation_picker),
                    key="operation_picker",
                )
            if st.session_state.operation_last_name != current_operation:
                st.session_state.operation_last_name = current_operation
                st.session_state.operation_minutes = OPERATION_CATALOG[current_operation].minutes
            with machine_col:
                st.text_input("Machine", value=OPERATION_CATALOG[current_operation].machine, disabled=True)
            with time_col:
                st.number_input(
                    "Time (min)",
                    min_value=1,
                    max_value=99,
                    step=1,
                    key="operation_minutes",
                )

            btn_add, btn_clear, btn_finish = st.columns(3)
            with btn_add:
                if st.button("Add Operation", use_container_width=True):
                    st.session_state.draft_ops.append(
                        DraftOperation(
                            name=current_operation,
                            minutes=int(st.session_state.operation_minutes),
                        )
                    )
                    st.session_state.order_locked = True
                    st.rerun()
            with btn_clear:
                if st.button("Clear Draft", use_container_width=True):
                    reset_metadata(clear_metadata=True)
                    st.rerun()
            with btn_finish:
                if st.button("Finish Order", use_container_width=True, type="primary"):
                    if not st.session_state.customer_field or not st.session_state.item_name_field or not st.session_state.draft_ops:
                        st.warning("Fill metadata and add at least one operation before finishing.")
                    else:
                        new_order = build_order(
                            order_id=st.session_state.order_id_field,
                            customer=st.session_state.customer_field,
                            item_name=st.session_state.item_name_field,
                            priority=int(st.session_state.priority_field),
                            due_date=st.session_state.due_date_field,
                            notes=st.session_state.notes_field,
                            operations=st.session_state.draft_ops,
                        )
                        st.session_state.orders.append(new_order)
                        st.session_state.selected_order = new_order.order_id
                        st.session_state.execution_focus_order = new_order.order_id
                        st.session_state.next_order_no += 1
                        sync_order_id()
                        st.session_state.draft_ops = []
                        st.session_state.order_locked = True
                        sync_operation_defaults()
                        st.success(f"Order {new_order.order_id} added.")
                        st.rerun()

    with right:
        with st.container(border=True):
            st.markdown("**Catalog**")
            catalog_df = pd.DataFrame(
                [
                    {"Operation": item.name, "Machine": item.machine, "Time": item.minutes, "Description": item.description}
                    for item in OPERATION_CATALOG.values()
                ]
            )
            st.dataframe(catalog_df, use_container_width=True, hide_index=True)

            st.markdown("**Draft Preview**")
            if st.session_state.draft_ops:
                draft_rows = [{"Seq": 0, "Step": "Loading", "Machine": "-", "Time (min)": 0}]
                for index, op in enumerate(st.session_state.draft_ops, start=1):
                    template = OPERATION_CATALOG[op.name]
                    draft_rows.append(
                        {
                            "Seq": index,
                            "Step": template.name,
                            "Machine": template.machine,
                            "Time (min)": op.minutes,
                        }
                    )
                draft_rows.append({"Seq": len(st.session_state.draft_ops) + 1, "Step": "Unloading", "Machine": "-", "Time (min)": 0})
                st.dataframe(pd.DataFrame(draft_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No operations added yet.")


def render_order_list() -> None:
    st.subheader("List of Orders")
    if not st.session_state.orders:
        st.info("No orders created yet.")
        return

    orders = sort_orders(st.session_state.orders, st.session_state.scheduler_mode)
    summary_df = pd.DataFrame([queue_summary(order) for order in orders])
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    chosen = st.selectbox("Select order to inspect", options=[order.order_id for order in orders], key="order_picker")
    st.session_state.selected_order = chosen
    selected = next(order for order in orders if order.order_id == chosen)

    st.markdown("**Order Details**")
    detail_left, detail_right = st.columns([1.1, 0.9])
    with detail_left:
        st.write(f"**Customer:** {selected.customer}")
        st.write(f"**Item:** {selected.item_name}")
        st.write(f"**Priority:** {selected.priority}")
        st.write(f"**Status:** {selected.status}")
        st.write(f"**Created:** {selected.created_at.strftime('%Y-%m-%d %H:%M:%S')}")
        if selected.due_date:
            st.write(f"**Due Date:** {selected.due_date}")
    with detail_right:
        st.write("**Route Tree**")
        route_rows = [{"Seq": 0, "Step": "Loading", "Machine": "-", "Time (min)": 0, "Status": "Fixed"}]
        for index, step in enumerate(selected.operations, start=1):
            route_rows.append(
                {
                    "Seq": index,
                    "Step": step.name,
                    "Machine": step.machine,
                    "Time (min)": step.minutes,
                    "Status": step.status,
                }
            )
        route_rows.append({"Seq": len(selected.operations) + 1, "Step": "Unloading", "Machine": "-", "Time (min)": 0, "Status": "Fixed"})
        st.dataframe(pd.DataFrame(route_rows), use_container_width=True, hide_index=True)


def render_scheduler_tab() -> None:
    st.subheader("Scheduling")
    if not st.session_state.orders:
        st.info("Create at least one order to see the scheduler.")
        return

    mode_col, action_col = st.columns([1, 1])
    with mode_col:
        st.session_state.scheduler_mode = st.radio("Scheduler mode", ["Static", "Dynamic"], horizontal=True, index=1 if st.session_state.scheduler_mode == "Dynamic" else 0)
    with action_col:
        if st.button("Run Scheduler", use_container_width=True):
            ordered = sort_orders(st.session_state.orders, st.session_state.scheduler_mode)
            for order in ordered:
                if order.status == "Queued" and order.queue_seconds_remaining == 0:
                    order.queue_seconds_remaining = max(2, len(order.operations) + 1)
            if ordered:
                st.session_state.selected_order = ordered[0].order_id
                if ordered[0].status == "Queued":
                    ordered[0].status = "Running"
                    ordered[0].queue_seconds_remaining = max(2, len(ordered[0].operations))
                st.success(f"Next order: {ordered[0].order_id}")

    queue_df = pd.DataFrame([queue_summary(order) for order in sort_orders(st.session_state.orders, st.session_state.scheduler_mode)])
    st.dataframe(queue_df, use_container_width=True, hide_index=True)
    st.markdown("**Scheduling Notes**")
    st.write("Static mode sorts by Order ID. Dynamic mode sorts by higher priority first, then by age.")


def render_execution_card(order: JobOrder, focused: bool) -> None:
    with st.container(border=True):
        if focused:
            st.markdown(f"### Active Order: {order.order_id}")
        else:
            st.markdown(f"**{order.order_id}**")
        st.write(f"Customer: {order.customer}")
        st.write(f"Item: {order.item_name}")
        st.write(f"Status: {order.status}")
        st.write(f"Current Step: {next_step(order)}")
        st.write(f"Queue Time Remaining: {order.queue_seconds_remaining}s")

        progress = 0 if not order.operations else int((order.current_step_index / len(order.operations)) * 100)
        st.progress(progress)
        st.caption("Execution progress")

        if focused:
            row_prev, row_adv, row_done = st.columns(3)
            with row_prev:
                if st.button("Previous", key=f"prev_{order.order_id}", use_container_width=True):
                    if order.current_step_index > 0:
                        order.current_step_index -= 1
                        order.operations[order.current_step_index].status = "Pending"
                        order.status = "Running"
                        st.rerun()
            with row_adv:
                if st.button("Advance", key=f"advance_{order.order_id}", use_container_width=True):
                    advance_order(order)
                    st.session_state.execution_focus_order = order.order_id
                    st.rerun()
            with row_done:
                if st.button("Complete", key=f"done_{order.order_id}", use_container_width=True):
                    next_focus = next_execution_focus(st.session_state.orders, st.session_state.scheduler_mode, order.order_id)
                    complete_order(order)
                    st.session_state.execution_focus_order = next_focus
                    st.session_state.selected_order = st.session_state.execution_focus_order
                    st.rerun()

            step_rows = [{"Seq": 0, "Step": "Loading", "Machine": "-", "Time (min)": 0, "Status": "Fixed"}]
            for step_index, step in enumerate(order.operations, start=1):
                step_rows.append(
                    {
                        "Seq": step_index,
                        "Step": step.name,
                        "Machine": step.machine,
                        "Time (min)": step.minutes,
                        "Status": step.status,
                    }
                )
            step_rows.append({"Seq": len(order.operations) + 1, "Step": "Unloading", "Machine": "-", "Time (min)": 0, "Status": "Fixed"})
            st.dataframe(pd.DataFrame(step_rows), use_container_width=True, hide_index=True)
        else:
            if st.button("Focus", key=f"focus_{order.order_id}", use_container_width=True):
                st.session_state.execution_focus_order = order.order_id
                st.session_state.selected_order = order.order_id
                st.rerun()


def render_execution_tab() -> None:
    st.subheader("Execution")
    if not st.session_state.orders:
        st.info("No order selected.")
        return

    tick_scheduler(st.session_state.orders)
    active_orders = [order for order in sort_orders(st.session_state.orders, st.session_state.scheduler_mode) if order.status not in {"Completed", "Cancelled"}]
    if not active_orders:
        st.success("All orders are completed.")
        return

    active_ids = [order.order_id for order in active_orders]
    if st.session_state.execution_focus_order not in active_ids:
        st.session_state.execution_focus_order = active_ids[0]
        st.session_state.selected_order = active_ids[0]

    st.markdown("**Active Jobs**")
    for order in active_orders:
        render_execution_card(order, focused=order.order_id == st.session_state.execution_focus_order)


def render_catalog_tab() -> None:
    st.subheader("Catalog")
    left, right = st.columns([1, 1])
    with left:
        st.markdown("**Operation Catalog**")
        catalog_df = pd.DataFrame(
            [
                {"Operation": item.name, "Machine": item.machine, "Time": item.minutes, "Description": item.description}
                for item in OPERATION_CATALOG.values()
            ]
        )
        st.dataframe(catalog_df, use_container_width=True, hide_index=True)
    with right:
        st.markdown("**FPU Basics**")
        basics_df = pd.DataFrame([{"Item": key, "Value": value} for key, value in FMS_INFO.items()])
        st.dataframe(basics_df, use_container_width=True, hide_index=True)


def main() -> None:
    init_state()
    app_style()
    st_autorefresh(interval=1000, key="fpu_refresh")
    header()
    render_summary_strip()
    sidebar_controls()

    tabs = st.tabs(["Orders/Jobs", "Scheduling", "Execution", "Catalog"])
    with tabs[0]:
        render_order_builder()
        st.divider()
        render_order_list()
    with tabs[1]:
        render_scheduler_tab()
    with tabs[2]:
        render_execution_tab()
    with tabs[3]:
        render_catalog_tab()


if __name__ == "__main__":
    main()
