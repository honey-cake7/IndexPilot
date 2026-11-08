import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class GenerationOptions(BaseModel):
    model_config = ConfigDict(extra="forbid")
    max_columns: int = Field(default=3, ge=1, le=3)
    max_candidates: int = Field(default=32, ge=1, le=32)


class CandidateRequest(GenerationOptions):
    plan_ids: list[uuid.UUID] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def distinct_sources(self):
        if len(set(self.plan_ids)) != len(self.plan_ids):
            raise ValueError("Source plan identifiers must be distinct")
        return self


class OperatorClass(BaseModel):
    oid: int
    schema_name: str
    name: str


class CandidateKey(BaseModel):
    column: str
    attribute_number: int
    type_oid: int
    operator_class: OperatorClass
    collation_oid: int
    collation_schema: str | None
    collation_name: str | None
    descending: bool = False
    nulls_first: bool = False


class CandidateDefinition(BaseModel):
    signature: str
    schema_name: str
    table_name: str
    table_oid: int
    index_name: str
    method: Literal["btree"] = "btree"
    keys: list[CandidateKey]
    ddl: str


class CandidateEvidence(BaseModel):
    plan_id: uuid.UUID
    alias: str
    reason: str
    explanation: str


class CandidateDecision(BaseModel):
    definition: CandidateDefinition
    status: Literal["proposed", "rejected"]
    rejection_reason: str | None = None
    existing_indexes: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    evidence: list[CandidateEvidence]
    evaluation_status: Literal["not_evaluated"] = "not_evaluated"
    estimated_size_bytes: None = None
    estimated_improvement_pct: None = None


class CandidateView(CandidateDecision):
    id: uuid.UUID


class GenerationResult(BaseModel):
    proposed: list[CandidateDecision]
    rejected: list[CandidateDecision]
    attempts: int
    unique_considered: int
    search_truncated: bool
    warnings: list[str]


class CandidateBatchView(BaseModel):
    id: uuid.UUID
    created_at: datetime
    catalog_observed_at: datetime
    source_plan_ids: list[uuid.UUID]
    options: GenerationOptions
    proposed: list[CandidateView]
    rejected: list[CandidateView]
    attempts: int
    unique_considered: int
    search_truncated: bool
    warnings: list[str]


class CandidateBatchSummary(BaseModel):
    id: uuid.UUID
    created_at: datetime
    catalog_observed_at: datetime
    search_truncated: bool
