"""Class duration and section day patterns for theory vs lab courses."""

from __future__ import annotations

from datetime import datetime, timedelta

COURSE_TYPE_DURATIONS: dict[str, int] = {
    "theory": 80,
    "lab": 150,
}

THEORY_SCHEDULE_KEYS = frozenset({"sat_tue", "sun_wed"})
LAB_SCHEDULE_KEYS = frozenset({"sat", "sun", "mon", "tue", "wed"})

THEORY_PATTERNS: dict[str, dict[str, object]] = {
    "sat_tue": {"label": "Saturday – Tuesday", "day_ids": [6, 2]},
    "sun_wed": {"label": "Sunday – Wednesday", "day_ids": [0, 3]},
}

LAB_DAYS: dict[str, dict[str, object]] = {
    "sat": {"label": "Saturday", "day_id": 6},
    "sun": {"label": "Sunday", "day_id": 0},
    "mon": {"label": "Monday", "day_id": 1},
    "tue": {"label": "Tuesday", "day_id": 2},
    "wed": {"label": "Wednesday", "day_id": 3},
}


def duration_minutes_for_type(course_type_code: str) -> int:
    return COURSE_TYPE_DURATIONS.get(course_type_code, COURSE_TYPE_DURATIONS["theory"])


def normalize_time_value(value: str) -> str:
    clean = value.strip()
    if len(clean) == 5:
        return f"{clean}:00"
    return clean


def add_minutes_to_time(starts_at: str, minutes: int) -> str:
    fmt = "%H:%M:%S" if starts_at.count(":") == 2 else "%H:%M"
    start = datetime.strptime(starts_at, fmt)
    end = start + timedelta(minutes=minutes)
    return end.strftime("%H:%M:%S")


def validate_schedule_key(course_type_code: str, schedule_key: str) -> None:
    code = course_type_code.lower()
    key = schedule_key.lower()
    if code == "theory":
        if key not in THEORY_SCHEDULE_KEYS:
            raise ValueError(
                "Theory sections must use Saturday–Tuesday or Sunday–Wednesday"
            )
        return
    if code == "lab":
        if key not in LAB_SCHEDULE_KEYS:
            raise ValueError(
                "Lab sections must use Saturday, Sunday, Monday, Tuesday, or Wednesday"
            )
        return
    raise ValueError(f"Unknown course type: {course_type_code}")


def day_ids_for_schedule(course_type_code: str, schedule_key: str) -> list[int]:
    validate_schedule_key(course_type_code, schedule_key)
    key = schedule_key.lower()
    if course_type_code.lower() == "theory":
        return list(THEORY_PATTERNS[key]["day_ids"])  # type: ignore[arg-type]
    return [int(LAB_DAYS[key]["day_id"])]


def schedule_label(course_type_code: str, schedule_key: str) -> str:
    key = schedule_key.lower()
    if course_type_code.lower() == "theory":
        return str(THEORY_PATTERNS[key]["label"])
    return str(LAB_DAYS[key]["label"])
