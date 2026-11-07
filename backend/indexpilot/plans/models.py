import uuid
from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

from indexpilot.sql.models import SQLAnalysis

Cost = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class PlanNode(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    node_type: str = Field(min_length=1)
    relation_name: str | None = None
    schema_name: str | None = None
    alias: str | None = None
    index_name: str | None = None
    startup_cost: Cost | None = None
    total_cost: Cost | None = None
    estimated_rows: Annotated[int, Field(ge=0)] | None = None
    estimated_width: Annotated[int, Field(ge=0)] | None = None
    index_condition: str | None = None
    recheck_condition: str | None = None
    filter_condition: str | None = None
    join_conditions: dict[str, str] = Field(default_factory=dict)
    sort_keys: list[str] = Field(default_factory=list)
    group_keys: list[str] = Field(default_factory=list)
    parent_relationship: str | None = None
    subplan_name: str | None = None
    join_type: str | None = None
    parallel_aware: bool = False
    children: list["PlanNode"] = Field(default_factory=list)


class PlanObservation(BaseModel):
    node_path: str
    node_type: str
    message: str
    estimated_output_fraction: float | None = None


class PlanDocument(BaseModel):
    root: PlanNode
    node_count: int
    cost_unit: Literal["planner_cost"] = "planner_cost"
    execution_measured: Literal[False] = False
    observations: list[PlanObservation]
    warnings: list[str]


class PlanRecord(BaseModel):
    id: uuid.UUID
    scenario_id: uuid.UUID | None
    captured_at: datetime
    database: str
    server_version: str
    original_sql: str
    frequency: float
    analysis: SQLAnalysis
    plan: PlanDocument
    raw_explain: list[dict[str, JsonValue]]
    planner_settings: dict[str, str]


class PlanSummary(BaseModel):
    id: uuid.UUID
    scenario_id: uuid.UUID | None
    captured_at: datetime
    root_node_type: str
    total_cost: float | None
    cost_unit: Literal["planner_cost"] = "planner_cost"
