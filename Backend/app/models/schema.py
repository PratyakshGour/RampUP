
from typing import Any
from pydantic import BaseModel, Field


# ---- Graph ----
class GraphNode(BaseModel):
    id: str
    label: str                      # Employee, Skill, Decision, ...
    name: str = ""
    props: dict[str, Any] = Field(default_factory=dict)

class GraphEdge(BaseModel):
    source: str
    target: str
    type: str                       # HAS_SKILL, DERIVED_FROM, ...

class Subgraph(BaseModel):
    nodes: list[GraphNode] = Field(default_factory=list)
    edges: list[GraphEdge] = Field(default_factory=list)
    highlight_nodes: list[str] = Field(default_factory=list) # ids on the answer path
    highlight_edges: list[str] = Field(default_factory=list) # "source|type|target"


# ---- Chat ----
class ChatRequest(BaseModel):
    message: str
    employee_id: str | None = None
    session_id: str | None = None

class Citation(BaseModel):
    id: str                         # "S1"
    title: str
    type: str                       # Document | Decision | Resource | Task | Graph
    snippet: str = ""
    node_id: str | None = None      # lets UI highlight it in the graph

class ChatResponse(BaseModel):
    answer: str
    intent: str
    citations: list[Citation] = Field(default_factory=list)
    subgraph: Subgraph = Field(default_factory=Subgraph)
    session_id: str | None = None


# ---- Onboarding ----
class EmployeeSummary(BaseModel):
    id: str
    name: str
    role: str
    is_new_hire: bool
    project_name: str | None = None
    client_name: str | None = None

class ResourceItem(BaseModel):
    id: str
    title: str
    type: str
    url: str = ""
    duration_hours: float = 0

class SkillGap(BaseModel):
    skill_id: str
    skill_name: str
    needed: int
    has: int = 0
    resources: list[ResourceItem] = Field(default_factory=list)   # empty = planted "no resource" gap

class PlanItem(BaseModel):
    kind: str                       # resource | task
    id: str
    title: str
    why: str = ""
    hours: float = 0

class Mentor(BaseModel):
    id: str
    name: str
    skills: list[str] = Field(default_factory=list)

class PlanResponse(BaseModel):
    employee: EmployeeSummary
    mentor: Mentor | None = None
    gaps: list[SkillGap] = Field(default_factory=list)
    day30: list[PlanItem] = Field(default_factory=list)
    day60: list[PlanItem] = Field(default_factory=list)
    day90: list[PlanItem] = Field(default_factory=list)
    first_tasks: list[PlanItem] = Field(default_factory=list)


# ---- Ingest ----
class IngestResponse(BaseModel):
    document_id: str
    chunks_added: int
    nodes_created: list[GraphNode] = Field(default_factory=list)
    edges_created: list[GraphEdge] = Field(default_factory=list)
    subgraph: Subgraph = Field(default_factory=Subgraph)