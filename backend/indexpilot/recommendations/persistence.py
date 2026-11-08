from sqlalchemy import select
from sqlalchemy.orm import Session

from indexpilot.errors import DomainError
from indexpilot.metadata.models import (
    RecommendationIndexQuery,
    RecommendationQuery,
    RecommendationSet,
    RecommendationSetIndex,
)
from indexpilot.plans.explanations import explain_plan
from indexpilot.plans.parser import parse_explain
from indexpilot.recommendations.explain import SQL_WARNINGS
from indexpilot.recommendations.models import (
    DeploymentSQL,
    RecommendationSummary,
    RecommendationView,
    RecommendedIndex,
    RecommendedQuery,
    RelevantQuery,
)
from indexpilot.sql.models import SQLAnalysis


def get_recommendation(engine, identifier):
    with Session(engine) as db:
        row = db.get(RecommendationSet, identifier)
        if row is None:
            raise DomainError("not_found", "Recommendation was not found.", 404)
        links = list(
            db.scalars(
                select(RecommendationIndexQuery)
                .where(RecommendationIndexQuery.recommendation_id == identifier)
                .order_by(RecommendationIndexQuery.source_plan_id)
            )
        )
        indexes = [
            RecommendedIndex(
                candidate_id=index.candidate_id,
                selection_order=index.selection_order,
                source_trial_id=index.source_trial_id,
                definition=index.definition,
                estimated_size_bytes=index.estimated_size_bytes,
                explanation=index.explanation,
                relevant_queries=[
                    RelevantQuery(
                        source_plan_id=link.source_plan_id,
                        proposed_evidence=link.proposed_evidence,
                        used_in_final_plan=link.used_in_final_plan,
                    )
                    for link in links
                    if link.candidate_id == index.candidate_id
                ],
            )
            for index in db.scalars(
                select(RecommendationSetIndex)
                .where(RecommendationSetIndex.recommendation_id == identifier)
                .order_by(RecommendationSetIndex.selection_order)
            )
        ]
        queries = []
        for query in db.scalars(
            select(RecommendationQuery)
            .where(RecommendationQuery.recommendation_id == identifier)
            .order_by(RecommendationQuery.source_plan_id)
        ):
            analysis = SQLAnalysis.model_validate(query.analysis)
            queries.append(
                RecommendedQuery(
                    source_plan_id=query.source_plan_id,
                    original_sql=query.original_sql,
                    representative_sql=analysis.canonical_sql,
                    frequency=query.frequency,
                    statistics_observations=[
                        dict(
                            relation_oid=table.oid,
                            schema_name=table.schema_name,
                            table_name=table.name,
                            last_analyze=table.last_analyze,
                            last_autoanalyze=table.last_autoanalyze,
                        )
                        for table in analysis.tables
                    ],
                    baseline_plan=explain_plan(
                        parse_explain(query.baseline_raw_explain), analysis.tables
                    ),
                    hypothetical_plan=explain_plan(
                        parse_explain(query.hypothetical_raw_explain), analysis.tables
                    ),
                    baseline_raw_explain=query.baseline_raw_explain,
                    hypothetical_raw_explain=query.hypothetical_raw_explain,
                    explanation=query.explanation,
                )
            )
        return RecommendationView(
            id=row.id,
            optimization_id=row.optimization_id,
            created_at=row.created_at,
            explanation_version=row.explanation_version,
            provenance=row.provenance,
            options=row.options,
            summary=row.summary,
            warnings=row.warnings,
            indexes=indexes,
            queries=queries,
        )


def list_recommendations(engine, *, optimization_id=None, limit=50, offset=0):
    with Session(engine) as db:
        statement = select(RecommendationSet)
        if optimization_id is not None:
            statement = statement.where(RecommendationSet.optimization_id == optimization_id)
        rows = db.scalars(
            statement.order_by(RecommendationSet.created_at.desc(), RecommendationSet.id)
            .limit(limit)
            .offset(offset)
        )
        return [
            RecommendationSummary(
                id=row.id,
                optimization_id=row.optimization_id,
                created_at=row.created_at,
                selected_count=row.summary["selected_count"],
                estimated_size_bytes=row.summary["estimated_size_bytes"],
                estimated_read_improvement_pct=row.summary["estimated_read_improvement_pct"],
            )
            for row in rows
        ]


def deployment_sql(engine, identifier):
    with Session(engine) as db:
        if db.get(RecommendationSet, identifier) is None:
            raise DomainError("not_found", "Recommendation was not found.", 404)
        indexes = db.scalars(
            select(RecommendationSetIndex)
            .where(RecommendationSetIndex.recommendation_id == identifier)
            .order_by(RecommendationSetIndex.selection_order)
        )
        return DeploymentSQL(
            recommendation_id=identifier,
            warnings=SQL_WARNINGS,
            statements=[
                dict(candidate_id=index.candidate_id, sql=index.deployment_sql) for index in indexes
            ],
        )


def sql_artifact(artifact):
    lines = [f"-- IndexPilot recommendation {artifact.recommendation_id}"]
    lines.extend("-- " + warning for warning in artifact.warnings)
    if not artifact.statements:
        lines.append("-- Empty selection: no index commands.")
    lines.extend(statement.sql for statement in artifact.statements)
    return "\n".join(lines) + "\n"
