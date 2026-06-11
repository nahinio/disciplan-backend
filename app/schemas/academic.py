from pydantic import BaseModel, Field, field_validator


class CreateAnnouncementRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    is_pinned: bool = False


class UpdateAnnouncementRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1)
    is_pinned: bool | None = None


class CreateDoubtRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)


class AnswerDoubtRequest(BaseModel):
    body: str = Field(min_length=1)
    parent_answer_id: int | None = None


class CreateBlogPostRequest(BaseModel):
    course_code: str
    topic_id: int | None = Field(default=None, ge=1)
    title: str = Field(min_length=1, max_length=250)
    excerpt: str = Field(max_length=500)
    body_html: str = Field(min_length=1)
    read_time_min: int = Field(default=5, ge=1, le=120)
    cover_image_file_id: int | None = None
    tags: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("tags", mode="before")
    @classmethod
    def normalize_tags(cls, value: object) -> list[str]:
        raw: list[str]
        if value is None:
            return []
        if isinstance(value, str):
            raw = [part.strip() for part in value.split(",")]
        elif isinstance(value, list):
            raw = [str(part).strip() for part in value]
        else:
            return []

        seen: set[str] = set()
        out: list[str] = []
        for name in raw:
            if not name or len(name) > 80:
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(name)
        return out[:20]


class CreateCommentRequest(BaseModel):
    body: str = Field(min_length=1)
    parent_comment_id: int | None = None


class VoteRequest(BaseModel):
    direction: str = Field(pattern="^(up|down)$")


class CreateTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    course_code: str | None = None
    section_key: str | None = None
    priority_code: str = Field(default="medium")
    energy_level_code: str | None = None
    task_type_code: str | None = None
    planner_task_type_code: str | None = None
    description: str | None = None
    due_at: str | None = None
    estimated_effort_min: int | None = Field(default=None, ge=5, le=480)
    attachment_file_id: int | None = None


class UpdateTaskRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    course_code: str | None = None
    section_key: str | None = None
    priority_code: str | None = None
    energy_level_code: str | None = None
    task_type_code: str | None = None
    planner_task_type_code: str | None = None
    description: str | None = None
    due_at: str | None = None
    estimated_effort_min: int | None = Field(default=None, ge=5, le=480)
    attachment_file_id: int | None = None
    completion_percent: int | None = Field(default=None, ge=0, le=100)
    completed: bool | None = None
    skipped: bool | None = None
    completed_portion_percent: float | None = Field(default=None, ge=0, le=100)
    scheduled_for_date: str | None = None


class SetDailyEnergyRequest(BaseModel):
    energy_level_code: str = Field(pattern="^(low|medium|high)$")
    energy_date: str | None = None


class UpdateBlogPostRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=250)
    excerpt: str | None = Field(default=None, max_length=500)
    body_html: str | None = None
    read_time_min: int | None = Field(default=None, ge=1, le=120)
    cover_image_file_id: int | None = None


class CreateCalendarEventRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    starts_at: str
    ends_at: str
    course_code: str | None = None
    section_key: str | None = None
    description: str | None = None
    all_day: bool = False
    planner_task_type_code: str | None = None
    priority_code: str | None = "medium"
    energy_level_code: str | None = None
    estimated_effort_min: int | None = Field(default=None, ge=5, le=480)


class RecurrenceSlotRequest(BaseModel):
    day_of_week: int = Field(ge=0, le=6)
    starts_time: str = Field(pattern=r"^\d{2}:\d{2}(:\d{2})?$")
    duration_min: int = Field(default=60, ge=15, le=480)


class CreateEventPlanRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    scheduling_mode: str = Field(
        pattern="^(deadline_divide|grading_linked|one_time|recurring_weekly|calendar_only)$"
    )
    planner_task_type_code: str | None = None
    course_code: str | None = None
    section_key: str | None = None
    priority_code: str = Field(default="medium")
    energy_level_code: str | None = None
    estimated_effort_min: int | None = Field(default=None, ge=5, le=480)
    deadline_at: str | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    portal_id: int | None = None
    grade_component_id: int | None = None
    recurrence: list[RecurrenceSlotRequest] | None = None


class UpdateEventPlanRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    planner_task_type_code: str | None = None
    course_code: str | None = None
    section_key: str | None = None
    priority_code: str | None = None
    energy_level_code: str | None = None
    estimated_effort_min: int | None = Field(default=None, ge=5, le=480)
    deadline_at: str | None = None
    starts_at: str | None = None
    ends_at: str | None = None
    portal_id: int | None = None
    grade_component_id: int | None = None
    recurrence: list[RecurrenceSlotRequest] | None = None


class UpdateCalendarEventRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    starts_at: str | None = None
    ends_at: str | None = None
    course_code: str | None = None
    description: str | None = None
    all_day: bool | None = None


class DeleteAccountRequest(BaseModel):
    confirm_email: str = Field(min_length=3, max_length=255)


class UpdateProfileRequest(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=120)
    department_id: int | None = None
    bio: str | None = Field(default=None, max_length=500)
    avatar_file_id: int | None = None
    avatar_preset: str | None = Field(default=None, max_length=40)


class UpdatePreferencesRequest(BaseModel):
    theme: str | None = None
    notify_academic: bool | None = None
    notify_teams: bool | None = None
    notify_system: bool | None = None
    notify_messages: bool | None = None
