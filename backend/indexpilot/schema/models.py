from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CatalogModel(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)


class ColumnStatistics(CatalogModel):
    null_fraction: float
    average_width: int
    n_distinct: float
    estimated_distinct_values: float | None
    uniform_equality_selectivity: float | None
    correlation: float | None
    most_common_frequencies: list[float] | None
    most_common_values: str | None
    histogram_bounds: str | None


class ColumnInfo(CatalogModel):
    number: int
    name: str
    type_oid: int
    type_schema: str
    type_name: str
    formatted_type: str
    type_kind: str
    not_null: bool
    generated: str
    identity: str
    default_expression: str | None
    collation_oid: int
    collation_schema: str | None
    collation_name: str | None
    statistics: ColumnStatistics | None


class IndexKey(CatalogModel):
    position: int
    column: str | None
    attribute_number: int
    expression: str
    operator_class_oid: int
    operator_class_schema: str
    operator_class_name: str
    operator_class_default: bool
    collation_oid: int
    collation_schema: str | None
    collation_name: str | None
    descending: bool
    nulls_first: bool


class IndexInfo(CatalogModel):
    oid: int
    name: str
    schema_name: str
    method: str
    definition: str
    primary: bool
    unique: bool
    valid: bool
    ready: bool
    live: bool
    nulls_not_distinct: bool
    predicate: str | None
    expressions: str | None
    keys: list[IndexKey]
    included_columns: list[str]
    size_bytes: int
    scans: int | None
    tuples_read: int | None
    tuples_fetched: int | None


class ConstraintInfo(CatalogModel):
    name: str
    kind: str
    columns: list[str]
    definition: str
    validated: bool
    referenced_schema: str | None
    referenced_table: str | None
    referenced_columns: list[str]


class TableSummary(CatalogModel):
    oid: int
    schema_name: str
    name: str
    kind: str
    persistence: str
    access_method: str | None
    estimated_rows: float | None
    estimated_pages: int
    table_bytes: int
    indexes_bytes: int
    total_bytes: int
    row_security: bool
    has_rules: bool
    inheritance: bool
    can_select: bool
    can_use_schema: bool
    last_analyze: datetime | None
    last_autoanalyze: datetime | None


class TableInfo(TableSummary):
    columns: list[ColumnInfo]
    indexes: list[IndexInfo]
    constraints: list[ConstraintInfo]
    warnings: list[str]


class SchemaSnapshot(CatalogModel):
    database: str
    database_oid: int
    server_version: str
    observed_at: datetime
    schema_names: list[str]
    tables: list[TableSummary]
    total_tables: int
    offset: int
    warnings: list[str]
