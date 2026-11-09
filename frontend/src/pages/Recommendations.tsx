import { useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import { Download } from "lucide-react";
import { api, object, type Model } from "../api/client";
import { CostChart } from "../components/Charts";
import { PlanTree } from "./Explorer";
import {
  Busy,
  bytes,
  date,
  download,
  Empty,
  ErrorBox,
  fmt,
  Go,
  Json,
  Metric,
  PageTitle,
  Pager,
  Panel,
  short,
  Tag,
  Warnings,
} from "../components/ui";

export function Recommendations() {
  return <RecommendationWorkspace report={false} />;
}
export function Reports() {
  return <RecommendationWorkspace report />;
}
function RecommendationWorkspace({ report }: { report: boolean }) {
  const [params, setParams] = useSearchParams();
  const [offset, setOffset] = useState(0);
  const id = params.get("id") ?? "";
  const list = useQuery({
    queryKey: ["recommendations", offset],
    queryFn: () => api.recommendations(offset),
  });
  const rec = useQuery({
    queryKey: ["recommendation", id],
    queryFn: () => api.recommendation(id),
    enabled: !!id,
  });
  return (
    <>
      <PageTitle
        title={report ? "Reports" : "Recommendations"}
        description={
          report
            ? "Download saved analysis evidence and separately linked benchmark measurements."
            : "Understand the selected index set, query trade-offs and the evidence behind it."
        }
      />
      {report && (
        <p className="notice">
          Evidence downloads use saved recommendations. Durable, versioned
          reports and richer comparison tools are scheduled for Milestone 11.
        </p>
      )}
      <div className="explorer-layout">
        <Panel title="Saved recommendations">
          {list.isPending ? (
            <Busy />
          ) : list.isError ? (
            <ErrorBox error={list.error} />
          ) : !list.data.length ? (
            <Empty />
          ) : (
            <>
              <div className="record-list">
                {list.data.map((r) => (
                  <button
                    key={r.id}
                    className={id === r.id ? "selected" : ""}
                    onClick={() => setParams({ id: r.id })}
                  >
                    <strong>
                      {short(r.id)}{" "}
                      <span className="muted">
                        / {r.selected_count} indexes
                      </span>
                    </strong>
                    <small>
                      {bytes(r.estimated_size_bytes)} · {date(r.created_at)}
                    </small>
                  </button>
                ))}
              </div>
              <Pager
                offset={offset}
                count={list.data.length}
                onChange={setOffset}
              />
            </>
          )}
        </Panel>
        <div>
          {!id ? (
            <Panel>
              <Empty title="Choose a saved recommendation" />
            </Panel>
          ) : rec.isPending ? (
            <Busy />
          ) : rec.isError ? (
            <ErrorBox error={rec.error} />
          ) : report ? (
            <ReportDetail key={id} rec={rec.data} />
          ) : (
            <RecommendationDetail key={id} rec={rec.data} />
          )}
        </div>
      </div>
    </>
  );
}
export function RecommendationDetail({
  rec,
}: {
  rec: Model<"RecommendationView">;
}) {
  const deploy = useMutation({ mutationFn: () => api.deployment(rec.id) });
  const batchId = object(rec.provenance).batch_id;
  return (
    <>
      <Panel title={`Recommendation ${short(rec.id)}`}>
        <Tag>PLANNER ESTIMATE · NOT EXECUTION TIME</Tag>
        <p className="muted">{rec.summary.message}</p>
        <CostChart
          baseline={rec.summary.baseline_score.read_cost}
          final={rec.summary.final_score.read_cost}
        />
        <div className="metrics compact">
          <Metric
            label="Estimated size"
            value={bytes(rec.summary.estimated_size_bytes)}
            note={`Budget ${bytes(rec.summary.storage_budget_bytes)}`}
          />
          <Metric
            label="Estimated read gain"
            value={
              rec.summary.estimated_read_improvement_pct == null
                ? "Unknown"
                : `${fmt(rec.summary.estimated_read_improvement_pct)}%`
            }
            note="Frequency-weighted root costs"
          />
        </div>
        <div className="actions">
          <Go
            to={`/budget?optimization=${rec.optimization_id}${typeof batchId === "string" ? `&batch=${batchId}` : ""}`}
          >
            Rerun with a different budget
          </Go>
          <Go to={`/benchmarks?recommendation=${rec.id}`}>
            Benchmark this selection
          </Go>
          <Go to={`/reports?id=${rec.id}`}>Download evidence</Go>
        </div>
        <Warnings items={rec.warnings} />
      </Panel>
      <Panel title={`Selected indexes · ${rec.indexes.length}`}>
        {!rec.indexes.length ? (
          <Empty title="Empty selection">
            No feasible positive gain was found within the saved search limits.
            An empty selection is a valid result.
          </Empty>
        ) : (
          rec.indexes.map((idx) => (
            <article className="index-card" key={idx.candidate_id}>
              <div className="panel-heading">
                <h3>
                  <span className="index-number">{idx.selection_order}</span>
                  <code>{idx.definition.index_name}</code>
                </h3>
                <Tag tone="success">{bytes(idx.estimated_size_bytes)}</Tag>
              </div>
              <p className="mono">
                {idx.definition.schema_name}.{idx.definition.table_name} (
                {idx.definition.keys.map((k) => k.column).join(", ")})
              </p>
              <p>{idx.explanation.selection_reason}</p>
              <p className="muted small">
                Selection-step marginal read reduction:{" "}
                {fmt(idx.explanation.selection_step_read_cost_reduction)} cost
                units. This attribution depends on selection order.
              </p>
              <p className="muted small">{idx.explanation.write_overhead}</p>
              <Warnings items={idx.explanation.warnings} />
              <Json
                title="Query relevance and selected index specification"
                value={idx}
              />
            </article>
          ))
        )}
      </Panel>
      <Panel title="Query trade-offs">
        {rec.queries.map((q, i) => (
          <details className="candidate" key={q.source_plan_id}>
            <summary>
              <strong>Query {i + 1}</strong>
              <Tag tone={q.explanation.regression ? "warning" : ""}>
                {q.explanation.regression ? "ESTIMATED REGRESSION" : "ESTIMATE"}
              </Tag>
              <span>frequency {fmt(q.frequency)}</span>
            </summary>
            <pre>{q.original_sql}</pre>
            <div className="two-columns">
              <div>
                <h3>Baseline plan</h3>
                <PlanTree node={q.baseline_plan.root} />
              </div>
              <div>
                <h3>Hypothetical plan</h3>
                <PlanTree node={q.hypothetical_plan.root} />
              </div>
            </div>
            <Warnings items={q.explanation.warnings} />
            <Json
              title="Weighted query explanation and statistics"
              value={{
                explanation: q.explanation,
                statistics: q.statistics_observations,
              }}
            />
          </details>
        ))}
      </Panel>
      <Panel title="Review deployment SQL">
        <p className="muted">
          SQL is an export for human review. The dashboard does not execute
          these statements on the monitored target.
        </p>
        <button
          className="secondary"
          disabled={deploy.isPending}
          onClick={() => deploy.mutate()}
        >
          {deploy.isPending ? "Loading…" : "Show deployment SQL"}
        </button>
        <ErrorBox error={deploy.error} />
        {deploy.data && (
          <>
            <pre>
              {deploy.data.statements.map((s) => s.sql).join("\n\n") ||
                "-- No selected indexes."}
            </pre>
            <button
              className="secondary"
              onClick={() =>
                download(
                  `indexpilot-${rec.id}.sql`,
                  deploy.data!.statements.map((s) => s.sql).join("\n\n"),
                  true,
                )
              }
            >
              <Download size={16} />
              Download .sql
            </button>
            <Warnings items={deploy.data.warnings} />
          </>
        )}
      </Panel>
    </>
  );
}
function ReportDetail({ rec }: { rec: Model<"RecommendationView"> }) {
  const [offset, setOffset] = useState(0);
  const jobs = useQuery({
    queryKey: ["benchmark-links", rec.id, offset],
    queryFn: () => api.benchmarks(offset, rec.id),
  });
  const exportJob = useMutation({
    mutationFn: async (id: string) => ({
      job: await api.benchmark(id),
      measurements: await api.measurements(id),
    }),
    onSuccess: (evidence) =>
      download(`indexpilot-benchmark-${evidence.job.id}.json`, {
        export_kind: "saved_benchmark_evidence",
        units: {
          latency: "ms",
          throughput: "transactions/second",
          storage: "bytes",
        },
        ...evidence,
      }),
  });
  return (
    <>
      <Panel title="Saved analysis evidence">
        <Tag>RECOMMENDATION SNAPSHOT</Tag>
        <h3 className="mono">{short(rec.id)}</h3>
        <p className="muted">
          Saved {date(rec.created_at)}. Planner estimates include SQL,
          representative values, selected definitions, query explanations and
          provenance.
        </p>
        <p className="small">
          Downloads include query text and representative parameters. Share them
          only with intended recipients.
        </p>
        <button
          className="primary"
          onClick={() =>
            download(`indexpilot-analysis-${rec.id}.json`, {
              export_kind: "saved_recommendation_evidence",
              report_version: null,
              evidence_level: "planner_estimate",
              cost_unit: "planner_cost",
              missing_evidence: [
                "Measured runtime is not part of the recommendation snapshot. Download linked benchmark evidence separately.",
              ],
              recommendation: rec,
            })
          }
        >
          <Download size={16} />
          Download analysis JSON
        </button>
        <Json title="Preview saved recommendation" value={rec} />
      </Panel>
      <Panel title="Linked physical benchmarks">
        <ErrorBox error={exportJob.error} />
        {jobs.isPending ? (
          <Busy />
        ) : jobs.isError ? (
          <ErrorBox error={jobs.error} />
        ) : !jobs.data.length ? (
          <Empty title="No benchmark on this page">
            No measured outcome is inferred from planner costs.
          </Empty>
        ) : (
          <div className="record-list">
            {jobs.data.map((j) => (
              <div className="record-row" key={j.id}>
                <div>
                  <Go to={`/benchmarks?job=${j.id}`}>{short(j.id)}</Go>
                  <p className="muted small">
                    {date(j.created_at)} · {j.status} · cleanup{" "}
                    {j.cleanup_confirmed ? "verified" : "unconfirmed"}
                  </p>
                </div>
                <button
                  className="secondary"
                  disabled={exportJob.isPending}
                  onClick={() => exportJob.mutate(j.id)}
                >
                  <Download size={15} />
                  JSON
                </button>
              </div>
            ))}
          </div>
        )}
        <Pager
          offset={offset}
          count={jobs.data?.length ?? 0}
          onChange={setOffset}
        />
      </Panel>
    </>
  );
}
