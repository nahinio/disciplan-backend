from pydantic import BaseModel, Field


class CreateEnrollmentRequestBody(BaseModel):
    course_code: str = Field(min_length=1, max_length=20)
    section_label: str = Field(min_length=1, max_length=2)
    message: str | None = Field(default=None, max_length=500)


class AdminEnrollStudentBody(BaseModel):
    course_code: str = Field(min_length=1, max_length=20)
    section_label: str = Field(min_length=1, max_length=2)
