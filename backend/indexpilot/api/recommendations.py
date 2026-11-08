import uuid
from typing import Annotated

from fastapi import APIRouter, Query, Request, Response

from indexpilot.api.dependencies import get_engine
from indexpilot.recommendations.models import (
    DeploymentSQL,
    RecommendationRequest,
    RecommendationSummary,
    RecommendationView,
)
from indexpilot.recommendations.persistence import (
    deployment_sql,
    get_recommendation,
    list_recommendations,
    sql_artifact,
)
from indexpilot.recommendations.service import create_recommendation

router = APIRouter(prefix="/api/v1/recommendations", tags=["recommendation snapshots"])


@router.post("", response_model=RecommendationView, status_code=201)
def create(body: RecommendationRequest, request: Request, response: Response):
    result, created = create_recommendation(get_engine(request), body)
    response.status_code = 201 if created else 200
    return result


@router.get("", response_model=list[RecommendationSummary])
def history(
    request: Request,
    optimization_id: uuid.UUID | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
):
    return list_recommendations(
        get_engine(request), optimization_id=optimization_id, limit=limit, offset=offset
    )


@router.get("/{recommendation_id}", response_model=RecommendationView)
def recommendation(recommendation_id: uuid.UUID, request: Request):
    return get_recommendation(get_engine(request), recommendation_id)


@router.get("/{recommendation_id}/deployment-sql", response_model=DeploymentSQL)
def proposed_sql(recommendation_id: uuid.UUID, request: Request):
    return deployment_sql(get_engine(request), recommendation_id)


@router.get("/{recommendation_id}/deployment.sql", response_class=Response)
def download_sql(recommendation_id: uuid.UUID, request: Request):
    artifact = deployment_sql(get_engine(request), recommendation_id)
    return Response(
        sql_artifact(artifact),
        media_type="text/plain",
        headers={
            "Content-Disposition": f'attachment; filename="indexpilot-{recommendation_id}.sql"'
        },
    )
