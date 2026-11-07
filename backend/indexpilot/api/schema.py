from typing import Annotated

from fastapi import APIRouter, Query, Request

from indexpilot.db.connections import require_demo_identity, target_connection
from indexpilot.schema.catalogs import inspect_schema, inspect_table
from indexpilot.schema.models import SchemaSnapshot, TableInfo

router = APIRouter(prefix="/api/v1/schema", tags=["schema"])


@router.get("", response_model=SchemaSnapshot)
def schema_snapshot(
    request: Request,
    schema_name: str | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
):
    settings = request.app.state.settings
    with target_connection(settings) as connection:
        require_demo_identity(connection)
        return inspect_schema(
            connection,
            allowed_schemas=settings.analysis_schemas,
            schema=schema_name,
            limit=limit,
            offset=offset,
        )


@router.get("/table", response_model=TableInfo)
def table_snapshot(
    request: Request,
    table_name: Annotated[str, Query(min_length=1, max_length=63)],
    schema_name: str = "public",
    include_values: bool = False,
):
    settings = request.app.state.settings
    with target_connection(settings) as connection:
        require_demo_identity(connection)
        return inspect_table(
            connection,
            schema_name,
            table_name,
            allowed_schemas=settings.analysis_schemas,
            include_values=include_values,
        )
