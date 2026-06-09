from pydantic import BaseModel, Field, field_validator


class CreateForumThreadRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    thread_type_code: str = Field(default="discussion", pattern="^(doubt|advice|resource|discussion)$")
    image_file_ids: list[int] = Field(default_factory=list, max_length=6)


class CreateForumReplyRequest(BaseModel):
    body: str = Field(min_length=1)
    parent_reply_id: int | None = None


class UpdateForumThreadRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)


class UpdateForumReplyRequest(BaseModel):
    body: str = Field(min_length=1)


class CreateTeamRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    course_code: str
    section_label: str | None = None


class InviteTeamMemberRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)


class RespondInvitationRequest(BaseModel):
    accept: bool


class CreateTeamTaskRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    assignee_user_id: int | None = None
    priority_code: str = Field(default="medium")
    due_at: str | None = None


class CreateTeamDateRequest(BaseModel):
    label: str = Field(min_length=1, max_length=120)
    occurs_at: str


class CreateTeamAnnouncementRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)


class CreatePortalRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    assessment_type_code: str = Field(default="assign")
    opens_at: str
    closes_at: str
    max_score: float = Field(default=100.0, gt=0)


class UpdatePortalRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    opens_at: str | None = None
    closes_at: str | None = None
    max_score: float | None = Field(default=None, gt=0)


class SubmitAssessmentRequest(BaseModel):
    file_id: int


class GradeSubmissionRequest(BaseModel):
    score: float = Field(ge=0)
    feedback: str | None = None


class UpsertGradeRequest(BaseModel):
    component_code: str = Field(min_length=1, max_length=30)
    score: float = Field(ge=0)
    max_score: float = Field(default=100.0, gt=0)
    feedback: str | None = None


class CreateGradeComponentRequest(BaseModel):
    component_type: str = Field(pattern="^(ct|evaluation|attendance|portal|team)$")
    label: str = Field(min_length=1, max_length=80)
    component_code: str | None = Field(default=None, max_length=40)
    max_score: float = Field(gt=0)
    weight_percent: float = Field(default=0, ge=0, le=100)
    sort_order: int = Field(default=0, ge=0)


class UpdateGradeComponentRequest(BaseModel):
    label: str | None = Field(default=None, min_length=1, max_length=80)
    max_score: float | None = Field(default=None, gt=0)
    weight_percent: float | None = Field(default=None, ge=0, le=100)
    sort_order: int | None = Field(default=None, ge=0)
    is_active: bool | None = None


class CreateSectionResourceRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    resource_kind: str = Field(default="file", pattern="^(file|link)$")
    file_id: int | None = None
    external_url: str | None = Field(default=None, max_length=500)
    mime_category: str = Field(
        default="other", pattern="^(pdf|pptx|image|doc|other)$"
    )


class UpdateSectionResourceRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    external_url: str | None = Field(default=None, max_length=500)


class UpdateSectionPracticeProblemRequest(BaseModel):
    question: str | None = Field(default=None, min_length=1)
    answer: str | None = Field(default=None, min_length=1)
    topic_id: int | None = None


class CreateAnnouncementCommentRequest(BaseModel):
    body: str = Field(min_length=1)
    parent_comment_id: int | None = None


class PinAnnouncementCommentRequest(BaseModel):
    pinned: bool = True


class FacultyAssignTeamRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    course_code: str
    section_label: str
    leader_user_id: int
    member_user_ids: list[int] = Field(default_factory=list)


class UpdateTeamRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    leader_user_id: int | None = None
    add_member_user_ids: list[int] = Field(default_factory=list)
    remove_member_user_ids: list[int] = Field(default_factory=list)


class GradeTeamRequest(BaseModel):
    score: float = Field(ge=0)
    max_score: float = Field(gt=0)
    label: str = Field(default="Project", min_length=1, max_length=80)
    feedback: str | None = None


class CreatePracticeTopicRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    week_number: int | None = None
    sort_order: int = 0


class CreatePracticeProblemRequest(BaseModel):
    topic_id: int | None = None
    question: str = Field(min_length=1)
    answer: str = Field(min_length=1)
    assessment_type_code: str = Field(default="mid", pattern="^(ct|mid|final)$")
    difficulty_score: int = Field(default=3, ge=1, le=5)
    question_image_file_id: int | None = None
    answer_image_file_id: int | None = None
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
            if len(out) >= 20:
                break
        return out


class CreatePastPaperRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    exam_year: int = Field(ge=2000, le=2100)
    file_id: int


class AdminFacultyRosterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    display_name: str = Field(min_length=2, max_length=120)


class AdminUpdateUserRequest(BaseModel):
    role_code: str | None = Field(default=None, pattern="^(student|faculty|admin)$")
    status_code: str | None = Field(default=None, pattern="^(active|suspended|pending)$")
    display_name: str | None = Field(default=None, min_length=2, max_length=120)
    department_id: int | None = None


class AdminDeleteUserRequest(BaseModel):
    confirm_email: str = Field(min_length=3, max_length=255)
    delete_faculty_sections: bool = False


class AdminCreateDepartmentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    code: str | None = Field(default=None, min_length=2, max_length=20)


class AdminUpdateDepartmentRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)


class AdminCreateCourseRequest(BaseModel):
    code: str = Field(min_length=2, max_length=20)
    title: str = Field(min_length=1, max_length=200)
    department_id: int
    credit_hours: float = Field(default=3.0, gt=0)
    has_project: bool = False
    course_type_code: str = Field(default="theory", pattern="^(theory|lab)$")


class AdminCreateSectionRequest(BaseModel):
    course_code: str
    section_label: str = Field(min_length=1, max_length=10)
    room: str | None = None
    faculty_user_id: int | None = None
    schedule_key: str | None = Field(
        default=None,
        pattern="^(sat_tue|sun_wed|sat|sun|mon|tue|wed)$",
    )
    starts_at: str | None = Field(default=None, min_length=4, max_length=8)


class AdjustPointsRequest(BaseModel):
    delta: int
    reason: str | None = None


class AwardBadgeRequest(BaseModel):
    badge_code: str
    user_id: int


class ForumMoveRequest(BaseModel):
    target_course_code: str


class ForumMergeRequest(BaseModel):
    target_thread_id: int


class AdminGlobalAnnouncementRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1)
    is_active: bool = True
    scheduled_for: str | None = None
    target_audience: str = Field(default="all", pattern="^(all|student|faculty)$")


class AdminUpdateAnnouncementRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    body: str | None = Field(default=None, min_length=1)
    is_active: bool | None = None
    scheduled_for: str | None = None


class AdminUpdateSectionRequest(BaseModel):
    room: str | None = None
    faculty_user_id: int | None = None
    schedule_key: str | None = Field(
        default=None,
        pattern="^(sat_tue|sun_wed|sat|sun|mon|tue|wed)$",
    )
    starts_at: str | None = Field(default=None, min_length=4, max_length=8)


class CreateContentReportRequest(BaseModel):
    entity_type_code: str = Field(
        pattern="^(blog_post|blog_comment|forum_thread|forum_reply)$"
    )
    entity_id: int = Field(ge=1)
    reason_code: str = Field(min_length=1, max_length=40)
    notes: str | None = Field(default=None, max_length=2000)


class ResolveContentReportRequest(BaseModel):
    action: str = Field(pattern="^(resolved|dismissed)$")
    delete_content: bool = False


class AdminUpdateTopicRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
