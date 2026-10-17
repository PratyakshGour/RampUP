from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class PersonExtraction(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    role: str | None = Field(default=None, max_length=120)
    team: str | None = Field(default=None, max_length=120)
    source_excerpt: str = Field(default="", max_length=1200)
    new_hire: bool = False
    attended: bool = False
    works_on: list[str] = Field(default_factory=list, max_length=10)
    expertise_in: list[str] = Field(default_factory=list, max_length=12)

    @model_validator(mode="after")
    def validate_relationship_evidence(self):
        if (self.works_on or self.expertise_in) and not self.source_excerpt:
            raise ValueError("Person-to-project and expertise links need supporting evidence")
        return self


class ProjectExtraction(StrictModel):
    name: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=800)
    systems: list[str] = Field(default_factory=list, max_length=16)
    owner: str | None = Field(default=None, max_length=120)
    source_excerpt: str = Field(default="", max_length=1200)

    @model_validator(mode="after")
    def validate_relationship_evidence(self):
        if (self.systems or self.owner) and not self.source_excerpt:
            raise ValueError("Project ownership and system links need supporting evidence")
        return self


class SystemExtraction(StrictModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    source_excerpt: str = Field(min_length=1, max_length=1200)


class DecisionExtraction(StrictModel):
    summary: str = Field(min_length=1, max_length=500)
    status: Literal["confirmed", "proposed", "unresolved"]
    rationale: str = Field(default="", max_length=1200)
    project: str | None = Field(default=None, max_length=160)
    systems: list[str] = Field(default_factory=list, max_length=12)
    supersedes: str | None = Field(default=None, max_length=500)
    source_excerpt: str = Field(min_length=1, max_length=1200)
    source_section: str | None = Field(default=None, max_length=120)
    timestamp_start: str | None = Field(default=None, max_length=40)
    timestamp_end: str | None = Field(default=None, max_length=40)


class TaskExtraction(StrictModel):
    description: str = Field(min_length=1, max_length=500)
    status: Literal["open", "in_progress", "done", "blocked"] = "open"
    owner: str | None = Field(default=None, max_length=120)
    project: str | None = Field(default=None, max_length=160)
    due_date: str | None = Field(default=None, max_length=40)
    source_excerpt: str = Field(min_length=1, max_length=1200)
    source_section: str | None = Field(default=None, max_length=120)


class FactExtraction(StrictModel):
    content: str = Field(min_length=1, max_length=800)
    category: str = Field(default="technical", max_length=80)
    people: list[str] = Field(default_factory=list, max_length=12)
    projects: list[str] = Field(default_factory=list, max_length=12)
    systems: list[str] = Field(default_factory=list, max_length=12)
    source_excerpt: str = Field(min_length=1, max_length=1200)
    source_section: str | None = Field(default=None, max_length=120)
    timestamp_start: str | None = Field(default=None, max_length=40)
    timestamp_end: str | None = Field(default=None, max_length=40)


class TranscriptExtraction(StrictModel):
    people: list[PersonExtraction] = Field(default_factory=list, max_length=40)
    projects: list[ProjectExtraction] = Field(default_factory=list, max_length=20)
    systems: list[SystemExtraction] = Field(default_factory=list, max_length=40)
    decisions: list[DecisionExtraction] = Field(default_factory=list, max_length=30)
    tasks: list[TaskExtraction] = Field(default_factory=list, max_length=40)
    facts: list[FactExtraction] = Field(default_factory=list, max_length=60)

    @model_validator(mode="after")
    def validate_extraction_has_sources(self):
        for item in [*self.decisions, *self.tasks, *self.facts]:
            if not item.source_excerpt.strip():
                raise ValueError("Every decision, task, and fact needs a supporting excerpt")
        return self


class MeetingMetadata(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    meeting_date: date | None = None
    participants: list[str] = Field(default_factory=list, max_length=40)
    project_name: str | None = Field(default=None, max_length=160)
    source_name: str = Field(default="transcript.txt", max_length=255)


class Citation(StrictModel):
    meeting_id: str
    meeting_title: str
    meeting_date: str | None = None
    excerpt: str
    section: str | None = None
    entity_id: str
    entity_type: str
    timestamp_start: str | None = None
    timestamp_end: str | None = None


class RelatedEntity(StrictModel):
    id: str
    label: str
    name: str
    relationship: str | None = None


class ChatRequest(StrictModel):
    question: str = Field(min_length=3, max_length=1200)
    session_id: str | None = Field(default=None, max_length=100)

    @field_validator("question")
    @classmethod
    def question_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Question cannot be blank")
        return value.strip()


class ChatResponse(StrictModel):
    answer: str
    category: str
    evidence_strength: Literal["strong", "moderate", "limited", "none"]
    citations: list[Citation]
    related_entities: list[RelatedEntity]
    session_id: str
    answer_provider: Literal["gemini", "demo", "grounded_fallback", "evidence_only"] = "evidence_only"
    warning: str | None = None


class OnboardingRecommendation(StrictModel):
    title: str
    description: str
    reason: str
    entity_id: str | None = None
    citation: Citation | None = None


class OnboardingResponse(StrictModel):
    employee: dict
    is_sample_profile: bool = False
    recommendations: list[OnboardingRecommendation]
    suggested_questions: list[str]
    ai_enhanced: bool = False
    warning: str | None = None


class IngestionResult(StrictModel):
    meeting_id: str
    title: str
    status: Literal["processed", "duplicate", "processing_failed"]
    demo_mode: bool
    summary: dict[str, int] = Field(default_factory=dict)
    message: str
