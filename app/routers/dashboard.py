from datetime import date, datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.dependencies.auth import get_current_user
from app.db.session import get_connection, transaction
from app.repositories import academic_repo, dashboard_repo, task_planner_repo
from app.schemas.academic import (
    CreateCalendarEventRequest,
    CreateEventPlanRequest,
    CreateTaskRequest,
    SetDailyEnergyRequest,
    UpdateCalendarEventRequest,
    UpdateEventPlanRequest,
    UpdateTaskRequest,
)
from app.services import event_plan_service, lecture_task_service, task_planner_service

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


@router.get("/tasks")
async def list_tasks(user: dict = Depends(get_current_user)) -> dict:
    async with get_connection() as conn:
        items = await task_planner_repo.list_all_tasks(conn, user["id"])
    return {"items": items}


@router.get("/tasks/today")
async def list_tasks_today(
    user: dict = Depends(get_current_user),
    task_date: str | None = Query(default=None, alias="date"),
) -> dict:
    target = _parse_date(task_date) or date.today()
    items = await task_planner_service.list_today(
        user["id"], user["role_code"], target_date=target
    )
    return {"items": items, "date": target.isoformat()}


@router.get("/tasks/plan")
async def get_tasks_plan(
    user: dict = Depends(get_current_user),
    start_date: str | None = Query(default=None, alias="date"),
) -> dict:
    target = _parse_date(start_date) or date.today()
    items = await task_planner_service.list_plan(user["id"], target)
    return {"items": items, "start_date": target.isoformat()}


@router.get("/tasks/{task_id}")
async def get_task(task_id: int, user: dict = Depends(get_current_user)) -> dict:
    return await task_planner_service.get_task(user["id"], task_id)


@router.post("/tasks")
async def create_task(
    body: CreateTaskRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    task_id = await task_planner_service.create_task(user["id"], body)
    return {"id": task_id, "message": "Task created"}


@router.patch("/tasks/{task_id}")
async def update_task(
    task_id: int,
    body: UpdateTaskRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    await task_planner_service.update_task(user["id"], task_id, body)
    return {"message": "Task updated"}


@router.delete("/tasks/{task_id}")
async def delete_task(
    task_id: int,
    user: dict = Depends(get_current_user),
) -> dict:
    await task_planner_service.delete_task(user["id"], task_id)
    return {"message": "Task deleted"}


@router.post("/tasks/generate-lectures")
async def generate_lectures(
    user: dict = Depends(get_current_user),
    task_date: str | None = Query(default=None, alias="date"),
) -> dict:
    target = _parse_date(task_date) or date.today()
    count = await lecture_task_service.generate_lecture_tasks_for_user(
        user["id"], user["role_code"], target_date=target
    )
    return {"message": "Lecture tasks generated", "created": count}


@router.post("/energy")
async def set_daily_energy(
    body: SetDailyEnergyRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    target = _parse_date(body.energy_date) or date.today()
    await task_planner_service.set_energy(user["id"], body.energy_level_code, target)
    return {"message": "Energy level saved"}


@router.get("/energy/today")
async def get_daily_energy(
    user: dict = Depends(get_current_user),
    energy_date: str | None = Query(default=None, alias="date"),
) -> dict:
    target = _parse_date(energy_date) or date.today()
    row = await task_planner_service.get_energy(user["id"], target)
    return {"energy": row, "date": target.isoformat()}


@router.get("/routine")
async def get_routine(user: dict = Depends(get_current_user)) -> dict:
    items = await task_planner_service.get_routine(user["id"], user["role_code"])
    return {"items": items}


@router.get("/calendar")
async def list_calendar(
    user: dict = Depends(get_current_user),
    merged: bool = Query(default=True),
    from_dt: str | None = Query(default=None),
) -> dict:
    parsed = _parse_dt(from_dt)
    if merged:
        items = await task_planner_service.merged_calendar(user["id"], parsed)
        return {"items": items}
    async with get_connection() as conn:
        items = await dashboard_repo.list_calendar_events(conn, user["id"], from_dt=parsed)
    return {"items": items}


@router.get("/event-plans")
async def list_event_plans(user: dict = Depends(get_current_user)) -> dict:
    items = await event_plan_service.list_plans(user["id"])
    return {"items": items}


@router.get("/event-plans/{plan_id}")
async def get_event_plan(plan_id: int, user: dict = Depends(get_current_user)) -> dict:
    return await event_plan_service.get_plan_detail(user["id"], plan_id)


@router.post("/event-plans")
async def create_event_plan(
    body: CreateEventPlanRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    result = await event_plan_service.create_plan(user["id"], body)
    return {**result, "message": "Event plan created"}


@router.patch("/event-plans/{plan_id}")
async def update_event_plan(
    plan_id: int,
    body: UpdateEventPlanRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    result = await event_plan_service.update_plan(user["id"], plan_id, body)
    return {**result, "message": "Event plan updated"}


@router.delete("/event-plans/{plan_id}")
async def delete_event_plan(
    plan_id: int,
    user: dict = Depends(get_current_user),
) -> dict:
    await event_plan_service.delete_plan(user["id"], plan_id)
    return {"message": "Event plan deleted"}


@router.post("/calendar")
async def create_calendar_event(
    body: CreateCalendarEventRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    """Legacy calendar create — routes through event plan system as deadline_divide."""
    type_code = body.planner_task_type_code or "personal"
    divide_types = {
        "ct",
        "assignment",
        "presentation",
        "personal_goal",
        "lecture",
        "lecture_prep",
        "exam_quiz",
        "personal",
    }
    if type_code == "meeting":
        mode = "calendar_only"
    elif type_code == "grading":
        mode = "grading_linked"
    elif type_code in divide_types:
        mode = "deadline_divide"
    else:
        mode = "one_time"

    plan_body = CreateEventPlanRequest(
        title=body.title,
        description=body.description,
        scheduling_mode=mode,
        planner_task_type_code=type_code,
        course_code=body.course_code,
        section_key=body.section_key,
        priority_code=body.priority_code or "medium",
        energy_level_code=body.energy_level_code,
        estimated_effort_min=body.estimated_effort_min,
        deadline_at=body.starts_at if mode == "deadline_divide" else None,
        starts_at=body.starts_at if mode != "deadline_divide" else None,
        ends_at=body.ends_at if mode != "deadline_divide" else None,
    )
    result = await event_plan_service.create_plan(user["id"], plan_body)
    return {
        "id": result.get("calendar_event_id") or result["id"],
        "task_id": result.get("task_id"),
        "plan_id": result["id"],
        "message": "Event created",
    }


@router.patch("/calendar/{event_id}")
async def update_calendar_event(
    event_id: int,
    body: UpdateCalendarEventRequest,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        course_id = None
        if body.course_code:
            course = await academic_repo.get_course_by_code(conn, body.course_code)
            course_id = course["id"] if course else None
        ok = await dashboard_repo.update_calendar_event(
            conn,
            user["id"],
            event_id,
            title=body.title,
            description=body.description,
            starts_at=_parse_dt(body.starts_at) if body.starts_at else None,
            ends_at=_parse_dt(body.ends_at) if body.ends_at else None,
            course_id=course_id,
            all_day=body.all_day,
        )
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return {"message": "Event updated"}


@router.delete("/calendar/{event_id}")
async def delete_calendar_event(
    event_id: int,
    user: dict = Depends(get_current_user),
) -> dict:
    async with transaction() as conn:
        ok = await dashboard_repo.delete_calendar_event(conn, user["id"], event_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Event not found")
    return {"message": "Event deleted"}
