from pydantic import BaseModel, Field


class RoutineSection(BaseModel):
    course_code: str
    section_label: str


class CompleteOnboardingRequest(BaseModel):
    display_name: str = Field(min_length=2, max_length=120)
    department_id: int | None = None
    role_code: str | None = Field(default=None, pattern="^(student|faculty)$")
    sections: list[RoutineSection] = Field(min_length=1)
