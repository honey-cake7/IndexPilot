"""Render only a frozen report; never query current catalogs or execute SQL."""

import html
import json
import re

from indexpilot.reports.models import ReportDocument


def text(value):
    value = html.escape(str(value), quote=True).replace("\n", " ").replace("\r", " ")
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", value)


def block(value, language=""):
    # A query containing backticks cannot close its own fence and inject prose.
    longest = max((len(run) for run in re.findall(r"`+", value)), default=0)
    fence = "`" * max(3, longest + 1)
    return f"{fence}{language}\n{value}\n{fence}"


def number(value):
    return "Unknown" if value is None else str(value)


def markdown(report: ReportDocument):
    lines = [
        f"# {text(report.title)}",
        "",
        f"Report: {report.id}",
        f"Format: {report.format_version}",
        f"Created: {report.created_at.isoformat()}",
        f"Recommendation: {report.recommendation_id}",
        f"Optimization: {report.optimization_id}",
        f"Candidate batch: {report.batch_id}",
        "",
        "## Evidence and privacy policy",
        "",
        "Frozen historical evidence. Planner costs are estimates, not milliseconds.",
        text(report.policy.parameter_policy),
        "",
        "## Missing evidence and limitations",
        "",
    ]
    lines.extend(f"- {text(item)}" for item in report.missing_evidence)
    lines.extend(
        [
            "",
            "## Estimated workload result",
            "",
            f"- Storage budget: {report.summary.storage_budget_bytes} bytes",
            f"- Selected estimated size: {report.summary.estimated_size_bytes} bytes",
            "- Weighted baseline root cost: "
            f"{number(report.summary.baseline_score.read_cost)} planner_cost",
            "- Weighted final root cost: "
            f"{number(report.summary.final_score.read_cost)} planner_cost",
            "- Estimated read improvement: "
            f"{number(report.summary.estimated_read_improvement_pct)} percent",
            f"- Search stop: {text(report.summary.stop_reason)}; "
            f"complete: {report.summary.search_complete}",
            "",
            "## Settings and provenance",
            "",
            block(
                json.dumps(
                    {
                        "settings": report.settings.model_dump(mode="json"),
                        "provenance": report.provenance,
                    },
                    indent=2,
                ),
                "json",
            ),
            "",
            "## Queries",
            "",
        ]
    )
    for q in report.queries:
        lines.extend(
            [
                f"### Query {q.source_plan_id}",
                "",
                f"Frequency: {q.frequency}",
                f"Root cost: {q.explanation.baseline_cost} -> "
                f"{q.explanation.final_cost} planner_cost",
                "Weighted contribution: "
                f"{number(q.explanation.contribution_to_baseline_pct)} percent of baseline",
                "",
                "Original SQL:"
                if q.original_sql is not None
                else "Original SQL omitted by policy.",
            ]
        )
        if q.original_sql is not None:
            lines.extend(["", block(q.original_sql, "sql")])
        if q.representative_sql is not None:
            lines.extend(
                [
                    "",
                    "Representative SQL (contains bound values):",
                    "",
                    block(q.representative_sql, "sql"),
                ]
            )
        lines.extend(
            [
                "",
                block(
                    json.dumps(
                        {
                            "explanation": q.explanation.model_dump(mode="json"),
                            "statistics": [s.model_dump(mode="json") for s in q.statistics],
                        },
                        indent=2,
                    ),
                    "json",
                ),
                "",
            ]
        )
    lines.extend(["## Selected indexes", ""])
    if not report.indexes:
        lines.append("Empty selection: no indexes were selected.")
    for index in report.indexes:
        lines.extend(
            [
                f"### {text(index.index_name)}",
                "",
                f"Estimated size: {index.estimated_size_bytes} bytes",
                text(index.explanation.selection_reason),
                text(index.explanation.write_overhead),
            ]
        )
        if index.deployment_sql is not None:
            lines.extend(
                [
                    "",
                    "Deployment SQL for human review only:",
                    "",
                    block(index.deployment_sql, "sql"),
                ]
            )
    lines.extend(["", "## All candidate decisions", ""])
    for c in report.candidates:
        keys = ", ".join(k.column for k in c.keys)
        lines.append(
            f"- {c.candidate_id}: {text(c.schema_name)}.{text(c.table_name)} "
            f"({text(keys)}); generation={text(c.generation_status)}; "
            f"selected={c.selected}; reason={text(c.reason)}"
        )
    lines.extend(
        [
            "",
            "## Saved search trials",
            "",
            block(
                json.dumps([t.model_dump(mode="json") for t in report.search_trials], indent=2),
                "json",
            ),
            "",
            "## Physical benchmarks",
            "",
        ]
    )
    if not report.benchmarks:
        lines.append("No benchmark selected. No measured performance claim is made.")
    for b in report.benchmarks:
        lines.extend(
            [
                f"### Benchmark {b.id}",
                "",
                f"Status: {text(b.status)}; cleanup confirmed: {b.cleanup_confirmed}; "
                f"complete comparison: {b.complete_comparison}",
                f"Local dashboard: /benchmarks?job={b.id}",
                "",
                "Latency: ms; throughput: transactions/second; storage: bytes.",
                "Measurements from unsuccessful jobs are partial, not a completed comparison.",
                "",
                block(b.model_dump_json(indent=2), "json"),
                "",
            ]
        )
    lines.extend(["## Warnings", "", *[f"- {text(w)}" for w in report.warnings], ""])
    return "\n".join(lines)
