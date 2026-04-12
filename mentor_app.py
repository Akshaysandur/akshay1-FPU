from __future__ import annotations

import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

from mentor_scheduler.catalog import FMS_INFO, OPERATION_CATALOG
from mentor_scheduler.models import JobOrder
from mentor_scheduler.scheduler import advance_order, build_order, complete_order, next_step, queue_summary, sort_orders, tick_scheduler


st.set_page_config(page_title="FPU Job Scheduler", layout="wide")


def init_state() -> None:
    if "orders" not in st.session_state:
        st.session_state.orders: list[JobOrder] = []
    if "draft_ops" not in st.session_state:
        st.session_state.draft_ops: list[str] = []
    if "scheduler_mode" not in st.session_state:
        st.session_state.scheduler_mode = "Dynamic"
    if "selected_order" not in st.session_state:
        st.session_state.selected_order = ""
    if "next_order_no" not in st.session_state:
        st.session_state.next_order_no = 1
    if "order_locked" not in st.session_state:
        st.session_state.order_locked = False
    if "tab_view" not in st.session_state:
        st.session_state.tab_view = "Orders/Jobs"
    if "reset_order_form" not in st.session_state:
        st.session_state.reset_order_form = False
    if "order_form_version" not in st.session_state:
        st.session_state.order_form_version = 0


def app_style() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(59, 130, 246, 0.18), transparent 24%),
                radial-gradient(circle at bottom right, rgba(244, 114, 182, 0.08), transparent 24%),
                linear-gradient(180deg, #050816 0%, #0b1020 45%, #111827 100%);
            color: #e5eefb;
        }
        [data-testid="stSidebar"] {
            background: linear-gradient(180deg, #020617 0%, #0f172a 100%);
            border-right: 1px solid rgba(148, 163, 184, 0.12);
        }
        [data-testid="stSidebar"] * {
            color: #f8fafc;
        }
        .block-container {
            padding-top: 1rem;
            padding-bottom: 1rem;
        }
        .fpu-card {
            background: rgba(15, 23, 42, 0.82);
            border: 1px solid rgba(148, 163, 184, 0.16);
            border-radius: 18px;
            padding: 1rem 1.1rem;
            box-shadow: 0 18px 36px rgba(2, 6, 23, 0.25);
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
        [data-testid="stHorizontalBlock"] > div > div {
            gap: 0.75rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def header() -> None:
    st.title("FPU Job Scheduler")
    st.caption("Add orders, build operations step by step, then review scheduling and execution in separate tabs.")


def sidebar_controls() -> None:
    st.sidebar.header("FPU Basics")
    st.sidebar.write(f"Scheduler mode: **{st.session_state.scheduler_mode}**")
    st.sidebar.write("Loading and unloading are treated as zero-time steps.")
    st.sidebar.divider()
    st.sidebar.caption("Simple scheduler for FPU order management.")
    st.sidebar.subheader("Tabs")
    st.session_state.tab_view = st.sidebar.radio(
        "Navigation",
        ["Orders/Jobs", "Scheduling", "Execution", "Catalog"],
        label_visibility="collapsed",
    )


def render_order_builder() -> None:
    st.subheader("Add Order")
    left, right = st.columns([1.1, 0.9], gap="large")

    if "order_form" not in st.session_state:
        st.session_state.order_form = {
            "order_id": f"ORD-{st.session_state.next_order_no:03d}",
            "customer": "",
            "item_name": "",
            "due_date": "",
            "notes": "",
            "priority": 3,
        }

    if st.session_state.reset_order_form:
        st.session_state.order_form = {
            "order_id": f"ORD-{st.session_state.next_order_no:03d}",
            "customer": "",
            "item_name": "",
            "due_date": "",
            "notes": "",
            "priority": 3,
        }
        st.session_state.draft_ops = []
        st.session_state.order_locked = False
        st.session_state.reset_order_form = False
        st.session_state.order_form_version += 1

    form = st.session_state.order_form
    form_version = st.session_state.order_form_version

    with left:
        with st.container(border=True):
            st.markdown("**Job Metadata**")
            col1, col2 = st.columns(2)
            metadata_locked = st.session_state.order_locked
            with col1:
                order_id = st.text_input("Order ID", value=form["order_id"], disabled=metadata_locked, key=f"order_id_input_{form_version}")
                customer = st.text_input("Customer", placeholder="Customer name", value=form["customer"], disabled=metadata_locked, key=f"customer_input_{form_version}")
                priority = st.slider("Priority", 1, 5, form["priority"], disabled=metadata_locked, key=f"priority_input_{form_version}")
            with col2:
                item_name = st.text_input("Item / Job Name", placeholder="Part or product name", value=form["item_name"], disabled=metadata_locked, key=f"item_input_{form_version}")
                due_date = st.text_input("Due Date", placeholder="YYYY-MM-DD", value=form["due_date"], disabled=metadata_locked, key=f"due_input_{form_version}")
                notes = st.text_area("Notes", placeholder="Optional notes", value=form["notes"], height=110, disabled=metadata_locked, key=f"notes_input_{form_version}")

            st.markdown("**Operation Builder**")
            op_col, machine_col, time_col = st.columns([1.2, 1, 0.8])
            with op_col:
                operation = st.selectbox("Operation", options=list(OPERATION_CATALOG.keys()), index=0, key=f"operation_picker_{form_version}")
            with machine_col:
                st.text_input("Machine", value=OPERATION_CATALOG[operation].machine, disabled=True)
            with time_col:
                st.text_input("Time", value=f"{OPERATION_CATALOG[operation].minutes} min", disabled=True)

            btn_add, btn_clear, btn_finish = st.columns(3)
            with btn_add:
                if st.button("Add Operation", use_container_width=True):
                    st.session_state.draft_ops.append(operation)
                    st.session_state.order_locked = True
                    st.rerun()
            with btn_clear:
                if st.button("Clear Draft", use_container_width=True):
                    st.session_state.draft_ops = []
                    st.session_state.order_locked = False
                    st.rerun()
            with btn_finish:
                if st.button("Finish Order", use_container_width=True, type="primary"):
                    if not customer or not item_name or not st.session_state.draft_ops:
                        st.warning("Fill metadata and add at least one operation before finishing.")
                    else:
                        new_order = build_order(
                            order_id=order_id,
                            customer=customer,
                            item_name=item_name,
                            priority=priority,
                            due_date=due_date,
                            notes=notes,
                            operations=st.session_state.draft_ops,
                        )
                        st.session_state.orders.append(new_order)
                        st.session_state.selected_order = new_order.order_id
                        st.session_state.draft_ops = []
                        st.session_state.order_locked = False
                        st.session_state.next_order_no += 1
                        st.session_state.reset_order_form = True
                        st.success(f"Order {new_order.order_id} added.")
                        st.rerun()

    with right:
        with st.container(border=True):
            st.markdown("**Draft Preview**")
            if st.session_state.draft_ops:
                draft_rows = [
                    {"Seq": 0, "Step": "Loading", "Machine": "-", "Time (min)": 0},
                ]
                for index, op in enumerate(st.session_state.draft_ops, start=1):
                    template = OPERATION_CATALOG[op]
                    draft_rows.append(
                        {
                            "Seq": index,
                            "Step": template.name,
                            "Machine": template.machine,
                            "Time (min)": template.minutes,
                        }
                    )
                draft_rows.append({"Seq": len(st.session_state.draft_ops) + 1, "Step": "Unloading", "Machine": "-", "Time (min)": 0})
                st.dataframe(pd.DataFrame(draft_rows), use_container_width=True, hide_index=True)
            else:
                st.info("No operations added yet.")
            st.markdown("**Catalog**")
            catalog_df = pd.DataFrame(
                [
                    {"Operation": item.name, "Machine": item.machine, "Time": item.minutes, "Description": item.description}
                    for item in OPERATION_CATALOG.values()
                ]
            )
            st.dataframe(catalog_df, use_container_width=True, hide_index=True)


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
        route_rows = [
            {"Seq": 0, "Step": "Loading", "Machine": "-", "Time (min)": 0, "Status": "Fixed"},
        ]
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

    for index, order in enumerate(active_orders, start=1):
        with st.container(border=True):
            header_cols = st.columns([1.1, 0.9])
            with header_cols[0]:
                st.markdown(f"**{index}. Order {order.order_id}**")
                st.write(f"Customer: {order.customer}")
                st.write(f"Item: {order.item_name}")
                st.write(f"Status: {order.status}")
                st.write(f"Current Step: {next_step(order)}")
                st.write(f"Queue Time Remaining: {order.queue_seconds_remaining}s")
            with header_cols[1]:
                progress = 0 if not order.operations else int((order.current_step_index / len(order.operations)) * 100)
                st.progress(progress)
                st.caption("Execution progress")

            row_prev, row_adv, row_done = st.columns(3)
            with row_prev:
                if st.button("Previous", key=f"prev_{order.order_id}", use_container_width=True):
                    if order.current_step_index > 0:
                        order.current_step_index -= 1
                        order.operations[order.current_step_index].status = "Pending"
                        order.status = "Running"
                        st.session_state.selected_order = order.order_id
                        st.rerun()
            with row_adv:
                if st.button("Advance", key=f"advance_{order.order_id}", use_container_width=True):
                    advance_order(order)
                    st.session_state.selected_order = order.order_id
                    st.rerun()
            with row_done:
                if st.button("Complete", key=f"done_{order.order_id}", use_container_width=True):
                    complete_order(order)
                    remaining = [item for item in active_orders if item.order_id != order.order_id and item.status not in {"Completed", "Cancelled"}]
                    if remaining:
                        st.session_state.selected_order = remaining[0].order_id
                        if remaining[0].status == "Queued":
                            remaining[0].status = "Running"
                            remaining[0].queue_seconds_remaining = max(2, len(remaining[0].operations))
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
            step_rows.append(
                {
                    "Seq": len(order.operations) + 1,
                    "Step": "Unloading",
                    "Machine": "-",
                    "Time (min)": 0,
                    "Status": "Fixed",
                }
            )
            st.dataframe(pd.DataFrame(step_rows), use_container_width=True, hide_index=True)


def main() -> None:
    init_state()
    app_style()
    st_autorefresh(interval=1000, key="fpu_refresh")
    header()
    sidebar_controls()

    if st.session_state.tab_view == "Orders/Jobs":
        render_order_builder()
        st.divider()
        render_order_list()
    elif st.session_state.tab_view == "Scheduling":
        render_scheduler_tab()
    elif st.session_state.tab_view == "Execution":
        render_execution_tab()
    else:
        st.subheader("FPU Basics")
        st.dataframe(
            pd.DataFrame([{"Item": key, "Value": value} for key, value in FMS_INFO.items()]),
            use_container_width=True,
            hide_index=True,
        )
        st.info("The interface keeps only the essential job entry, scheduling, and execution tracking.")


if __name__ == "__main__":
    main()
