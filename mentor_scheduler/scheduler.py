from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from mentor_scheduler.catalog import OPERATION_CATALOG
from mentor_scheduler.models import DraftOperation, JobOrder, OperationStep, SchedulerState

IST_TZ = ZoneInfo("Asia/Kolkata")


def build_operation(name: str, minutes: int | None = None) -> OperationStep:
    template = OPERATION_CATALOG[name]
    return OperationStep(name=template.name, machine=template.machine, minutes=template.minutes if minutes is None else minutes)


def build_order(
    order_id: str,
    customer: str,
    item_name: str,
    priority: int,
    due_date: str,
    notes: str,
    operations: list[DraftOperation],
) -> JobOrder:
    return JobOrder(
        order_id=order_id,
        customer=customer,
        item_name=item_name,
        priority=priority,
        due_date=due_date,
        notes=notes,
        created_at=datetime.now(IST_TZ),
        operations=[build_operation(item.name, item.minutes) for item in operations],
    )


def sort_orders(orders: list[JobOrder], mode: str) -> list[JobOrder]:
    if mode == "Static":
        return sorted(orders, key=lambda item: item.order_id)
    return sorted(orders, key=lambda item: (-item.priority, item.created_at, item.order_id))


def queue_summary(order: JobOrder) -> dict[str, object]:
    return {
        "Order ID": order.order_id,
        "Customer": order.customer,
        "Item": order.item_name,
        "Priority": order.priority,
        "Ops": len(order.operations),
        "Status": order.status,
        "Next Step": next_step(order),
        "Queue Time": f"{order.queue_seconds_remaining}s",
    }


def next_step(order: JobOrder) -> str:
    if order.current_step_index < len(order.operations):
        step = order.operations[order.current_step_index]
        return f"{step.name} / {step.machine}"
    return "Unloading"


def advance_order(order: JobOrder) -> JobOrder:
    if order.status in {"Completed", "Cancelled"}:
        return order

    if order.current_step_index < len(order.operations):
        order.operations[order.current_step_index].status = "Done"
        order.current_step_index += 1
        if order.current_step_index < len(order.operations):
            order.status = "Running"
        else:
            order.status = "Unloading"
            order.queue_seconds_remaining = 2
    else:
        order.status = "Completed"
    if order.status == "Completed":
        for step in order.operations:
            if step.status != "Done":
                step.status = "Done"
    return order


def complete_order(order: JobOrder) -> JobOrder:
    order.status = "Completed"
    order.current_step_index = len(order.operations)
    order.queue_seconds_remaining = 0
    for step in order.operations:
        step.status = "Done"
    return order


def tick_scheduler(orders: list[JobOrder]) -> list[JobOrder]:
    active_found = False
    for order in sorted(orders, key=lambda item: (item.status != "Running", item.priority, item.created_at)):
        if order.status in {"Completed", "Cancelled"}:
            continue
        if order.status == "Running" and not active_found:
            active_found = True
            if order.queue_seconds_remaining > 0:
                order.queue_seconds_remaining -= 1
            if order.queue_seconds_remaining == 0 and order.current_step_index < len(order.operations):
                advance_order(order)
            elif order.queue_seconds_remaining == 0 and order.current_step_index >= len(order.operations):
                order.status = "Completed"
        elif not active_found and order.status == "Queued":
            order.status = "Running"
            active_found = True
            if order.queue_seconds_remaining == 0:
                order.queue_seconds_remaining = 3
        elif order.status == "Unloading":
            if order.queue_seconds_remaining > 0:
                order.queue_seconds_remaining -= 1
            if order.queue_seconds_remaining == 0:
                complete_order(order)
    return orders


def make_scheduler_state(mode: str, active_order_id: str = "") -> SchedulerState:
    return SchedulerState(mode=mode, last_run=datetime.now(IST_TZ), active_order_id=active_order_id)
