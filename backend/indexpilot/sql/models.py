from typing import Literal

from pydantic import BaseModel

from indexpilot.schema.models import TableInfo


class ResolvedColumn(BaseModel):
    relation_oid: int
    schema_name: str
    table: str
    alias: str
    name: str
    type_oid: int


class RelationBinding(BaseModel):
    alias: str
    schema_name: str
    table: str
    relation_oid: int


class ColumnUsage(BaseModel):
    column: ResolvedColumn
    contexts: list[str]


class PredicateFeature(BaseModel):
    column: ResolvedColumn
    operator: str
    other_column: ResolvedColumn | None
    other_kind: Literal["literal", "column", "expression"]
    kind: Literal["equality", "range", "join", "column_comparison", "other"]
    context: str
    conjunction_only: bool
    join_type: str | None


class OrderFeature(BaseModel):
    column: ResolvedColumn | None
    expression: str
    direction: Literal["asc", "desc"]
    nulls_first: bool


class SQLAnalysis(BaseModel):
    canonical_sql: str
    relations: list[RelationBinding]
    columns: list[ColumnUsage]
    predicates: list[PredicateFeature]
    order_by: list[OrderFeature]
    tables: list[TableInfo]
    warnings: list[str]
