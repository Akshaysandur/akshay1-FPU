from __future__ import annotations

import pandas as pd
import streamlit as st

from mentor_scheduler.catalog import FMS_INFO, OPERATION_CATALOG
from mentor_scheduler.models import JobOrder
from mentor_scheduler.scheduler import advance_order, build_order, complete_order, next_step, queue_summary, sort_orders


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


def render_order_builder() -> None:
    st.subheader("Add Order")
    left, right = st.columns([1.1, 0.9], gap="large")

    with left:
        with st.container(border=True):
            st.markdown("**Job Metadata**")
            col1, col2 = st.columns(2)
            metadata_locked = st.session_state.order_locked
            with col1:
                order_id = st.text_input("Order ID", value=f"ORD-{st.session_state.next_order_no:03d}", disabled=metadata_locked)
                customer = st.text_input("Customer", placeholder="Customer name", disabled=metadata_locked)
                priority = st.slider("Priority", 1, 5, 3, disabled=metadata_locked)
            with col2:
                item_name = st.text_input("Item / Job Name", placeholder="Part or product name", disabled=metadata_locked)
                due_date = st.text_input("Due Date", placeholder="YYYY-MM-DD", disabled=metadata_locked)
                notes = st.text_area("Notes", placeholder="Optional notes", height=110, disabled=metadata_locked)

            st.markdown("**Operation Builder**")
            op_col, machine_col, time_col = st.columns([1.2, 1, 0.8])
            with op_col:
                operation = st.selectbox("Operation", options=list(OPERATION_CATALOG.keys()), index=0, key="operation_picker")
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
            st.session_state.selected_order = ordered[0].order_id
            for order in st.session_state.orders:
                if order.order_id == ordered[0].order_id:
                    order.status = "Running"
                elif order.status == "Queued":
                    order.status = "Queued"
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

    selected_id = st.session_state.selected_order or st.session_state.orders[0].order_id
    order = next(order for order in st.session_state.orders if order.order_id == selected_id)

    col1, col2 = st.columns([1.1, 0.9])
    with col1:
        st.markdown("**Active Order**")
        st.write(f"**Order ID:** {order.order_id}")
        st.write(f"**Status:** {order.status}")
        st.write(f"**Current Step:** {next_step(order)}")
        progress = 0 if not order.operations else int((order.current_step_index / len(order.operations)) * 100)
        st.progress(progress)

        btn_prev, btn_next, btn_done = st.columns(3)
        with btn_prev:
            if st.button("Previous", use_container_width=True):
                if order.current_step_index > 0:
                    order.current_step_index -= 1
                    order.operations[order.current_step_index].status = "Pending"
                    order.status = "Running"
                    st.rerun()
        with btn_next:
            if st.button("Advance", use_container_width=True):
                advance_order(order)
                st.rerun()
        with btn_done:
            if st.button("Complete", use_container_width=True):
                complete_order(order)
                st.rerun()

    with col2:
        st.markdown("**Step List**")
        rows = []
        rows.append({"Seq": 0, "Step": "Loading", "Machine": "-", "Time (min)": 0, "Status": "Fixed"})
        for step in order.operations:
            rows.append({"Seq": len(rows), "Step": step.name, "Machine": step.machine, "Time (min)": step.minutes, "Status": step.status})
        rows.append({"Seq": len(rows), "Step": "Unloading", "Machine": "-", "Time (min)": 0, "Status": "Fixed"})
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


def render_footer() -> None:
    st.caption("FPU order scheduler. No visual factory map, only job management and execution flow.")


def main() -> None:
    init_state()
    app_style()
    header()
    sidebar_controls()

    tab_orders, tab_scheduler, tab_execution, tab_catalog = st.tabs(["Orders/Jobs", "Scheduling", "Execution", "Catalog"])
    with tab_orders:
        render_order_builder()
        st.divider()
        render_order_list()
    with tab_scheduler:
        render_scheduler_tab()
    with tab_execution:
        render_execution_tab()
    with tab_catalog:
        st.subheader("FPU Basics")
        st.dataframe(
            pd.DataFrame([{"Item": key, "Value": value} for key, value in FMS_INFO.items()]),
            use_container_width=True,
            hide_index=True,
        )
        st.info("The interface keeps only the essential job entry, scheduling, and execution tracking.")

    render_footer()


if __name__ == "__main__":
    main()
