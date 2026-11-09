import { useState, type FormEvent } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Play, Save } from "lucide-react";
import { api, type Model } from "../api/client";
import { CostChart } from "../components/Charts";
import {
  Busy,
  bytes,
  date,
  Empty,
  ErrorBox,
  fmt,
  Json,
  Metric,
  PageTitle,
  Pager,
  Panel,
  short,
  Tag,
  Warnings,
} from "../components/ui";

export function budgetBytes(mib: string) {
  const value = Number(mib) * 1048576;
  if (
    !mib.trim() ||
    !Number.isFinite(value) ||
    value < 0 ||
    !Number.isSafeInteger(Math.round(value))
  )
    throw new Error(
      "Enter a nonnegative budget within JavaScript’s safe integer range.",
    );
  return Math.round(value);
}
export function Budget() {
  const [params, setParams] = useSearchParams();
  const [offset, setOffset] = useState(0);
  const id = params.get("batch") ?? "";
  const opt = params.get("optimization") ?? "";
  const list = useQuery({
    queryKey: ["batches", offset],
    queryFn: () => api.batches(offset),
  });
  const run = useQuery({
    queryKey: ["optimization", opt],
    queryFn: () => api.optimization(opt),
    enabled: !!opt,
  });
  const batchId = id || run.data?.batch_id || "";
  const batch = useQuery({
    queryKey: ["batch", batchId],
    queryFn: () => api.batch(batchId),
    enabled: !!batchId,
  });
  return (
    <>
      <PageTitle
        title="Budget Simulator"
        description="Rerun the real optimizer with a storage constraint. Each run saves a new result."
      />
      <Panel title="Candidate source">
        <label>
          Saved candidate batch
          <select
            value={batchId}
            onChange={(e) => setParams({ batch: e.target.value })}
          >
            <option value="">Choose a candidate batch</option>
            {batchId && !list.data?.some((b) => b.id === batchId) && (
              <option value={batchId}>
                {short(batchId)} · selected record
              </option>
            )}
            {list.data?.map((b) => (
              <option key={b.id} value={b.id}>
                {short(b.id)} · {date(b.created_at)}
              </option>
            ))}
          </select>
        </label>
        {list.isPending && <Busy />}
        <ErrorBox error={list.error} />
        <Pager
          offset={offset}
          count={list.data?.length ?? 0}
          onChange={setOffset}
        />
      </Panel>
      {opt && run.isPending ? (
        <Busy />
      ) : opt && run.isError ? (
        <ErrorBox error={run.error} />
      ) : !batchId ? (
        <Panel>
          <Empty title="Choose an analysis to optimize" />
        </Panel>
      ) : batch.isPending ? (
        <Busy />
      ) : batch.isError ? (
        <ErrorBox error={batch.error} />
      ) : (
        batch.data && (
          <BudgetForm
            key={`${batchId}-${opt}`}
            batch={batch.data}
            initial={run.data}
          />
        )
      )}
    </>
  );
}
function BudgetForm({
  batch,
  initial,
}: {
  batch: Model<"CandidateBatchView">;
  initial?: Model<"OptimizationRunView">;
}) {
  const [mib, setMib] = useState(
    String((initial?.options.storage_budget_bytes ?? 1048576) / 1048576),
  );
  const [maxIndexes, setMaxIndexes] = useState(
    String(initial?.options.max_selected_indexes ?? 8),
  );
  const [maxEvaluations, setMaxEvaluations] = useState(
    String(initial?.options.max_evaluations ?? 128),
  );
  const [penalty, setPenalty] = useState(
    String(initial?.options.write_penalty_cost_per_mib ?? 0),
  );
  const [regression, setRegression] = useState(
    initial?.options.max_query_regression_pct == null
      ? ""
      : String(initial.options.max_query_regression_pct),
  );
  const qc = useQueryClient();
  const nav = useNavigate();
  const [, setParams] = useSearchParams();
  const optimize = useMutation({
    mutationFn: () =>
      api.optimize({
        batch_id: batch.id,
        storage_budget_bytes: budgetBytes(mib),
        max_selected_indexes: Number(maxIndexes),
        max_evaluations: Number(maxEvaluations),
        write_penalty_cost_per_mib: Number(penalty),
        max_query_regression_pct: regression.trim() ? Number(regression) : null,
        write_weights: initial?.options.write_weights ?? {},
        frequency_basis:
          initial?.options.frequency_basis ?? "user_supplied_scenario",
      }),
    onSuccess: (data) => {
      qc.setQueryData(["optimization", data.id], data);
      void qc.invalidateQueries({ queryKey: ["overview"] });
      void qc.invalidateQueries({ queryKey: ["optimizations"] });
      setParams({ batch: batch.id, optimization: data.id });
    },
  });
  const save = useMutation({
    mutationFn: api.recommend,
    onSuccess: (data) => {
      void qc.invalidateQueries();
      nav(`/recommendations?id=${data.id}`);
    },
  });
  const result = initial;
  const changed =
    !!result &&
    (Math.round(Number(mib) * 1048576) !==
      result.options.storage_budget_bytes ||
      Number(maxIndexes) !== result.options.max_selected_indexes ||
      Number(maxEvaluations) !== result.options.max_evaluations ||
      Number(penalty) !== result.options.write_penalty_cost_per_mib ||
      (regression.trim() ? Number(regression) : null) !==
        result.options.max_query_regression_pct);
  function submit(e: FormEvent) {
    e.preventDefault();
    optimize.mutate();
  }
  return (
    <>
      <div className="two-columns">
        <Panel title="Storage & search">
          <form onSubmit={submit}>
            <fieldset disabled={optimize.isPending}>
              <label>
                Storage budget (MiB)
                <input
                  type="number"
                  required
                  min="0"
                  step="any"
                  value={mib}
                  onChange={(e) => setMib(e.target.value)}
                />
              </label>
              <label>
                Budget slider (MiB, 0–16)
                <input
                  type="range"
                  min="0"
                  max="16"
                  step="0.125"
                  value={Math.min(16, Math.max(0, Number(mib) || 0))}
                  onChange={(e) => setMib(e.target.value)}
                />
              </label>
              <p className="muted small">
                {bytes(Number(mib) * 1048576)} · estimated additional index
                bytes
              </p>
              <details>
                <summary>Search & write penalty options</summary>
                <label>
                  Maximum indexes
                  <input
                    required
                    type="number"
                    min="0"
                    max="32"
                    step="1"
                    value={maxIndexes}
                    onChange={(e) => setMaxIndexes(e.target.value)}
                  />
                </label>
                <label>
                  Evaluation limit
                  <input
                    required
                    type="number"
                    min="2"
                    max="1024"
                    step="1"
                    value={maxEvaluations}
                    onChange={(e) => setMaxEvaluations(e.target.value)}
                  />
                </label>
                <label>
                  Write penalty per MiB
                  <input
                    required
                    type="number"
                    min="0"
                    max="1000000000000"
                    step="any"
                    value={penalty}
                    onChange={(e) => setPenalty(e.target.value)}
                  />
                </label>
                <p className="muted small">
                  Heuristic planner-cost penalty, not measured write latency.
                  Saved per-candidate write weights are retained when rerunning
                  history.
                </p>
                <label>
                  Maximum query regression (%)
                  <input
                    type="number"
                    min="0"
                    max="1000000"
                    step="any"
                    placeholder="No configured limit"
                    value={regression}
                    onChange={(e) => setRegression(e.target.value)}
                  />
                </label>
              </details>
              <button className="primary" type="submit">
                <Play size={16} />
                {optimize.isPending
                  ? "Evaluating with HypoPG…"
                  : "Run optimization"}
              </button>
            </fieldset>
          </form>
          <ErrorBox error={optimize.error ?? save.error} />
          {changed && (
            <p className="notice">
              Settings changed. Run optimization to save results for this
              budget.
            </p>
          )}
        </Panel>
        <Panel title="Saved optimizer result">
          {!result ? (
            <Empty title="Ready for a real evaluation">
              Run optimization to compare complete index sets under this budget.
            </Empty>
          ) : (
            <>
              <div className="panel-heading">
                <Tag>PLANNER ESTIMATE</Tag>
                <code>{short(result.id)}</code>
              </div>
              <p className="muted small">
                Saved budget: {bytes(result.options.storage_budget_bytes)} ·{" "}
                {date(result.created_at)}
              </p>
              <CostChart
                baseline={result.result.baseline_score.read_cost}
                final={result.result.final_score.read_cost}
              />
              <div className="metrics compact">
                <Metric
                  label="Selected indexes"
                  value={result.result.selected_candidate_ids.length}
                  note={result.result.stop_reason.replaceAll("_", " ")}
                />
                <Metric
                  label="Estimated size"
                  value={bytes(result.result.final_score.storage_bytes)}
                  note="HypoPG size estimate"
                />
                <Metric
                  label="Estimated read gain"
                  value={
                    result.result.estimated_read_improvement_pct == null
                      ? "Unknown"
                      : `${fmt(result.result.estimated_read_improvement_pct)}%`
                  }
                  note={`${result.result.evaluations} evaluations · greedy search`}
                />
              </div>
              <button
                className="primary"
                disabled={save.isPending || optimize.isPending || changed}
                onClick={() => save.mutate(result.id)}
              >
                <Save size={16} />
                {save.isPending ? "Saving…" : "Save recommendation"}
              </button>
              <Warnings items={result.result.warnings} />
              <Json
                title="Search trials, scores and final verification"
                value={result}
              />
            </>
          )}
        </Panel>
      </div>
      <Panel
        title={`Candidate evidence · ${batch.proposed.length} proposed / ${batch.rejected.length} rejected`}
      >
        <Warnings items={batch.warnings} />
        {!batch.proposed.length && !batch.rejected.length ? (
          <Empty title="No candidates were generated">
            The empty index set remains a valid optimizer result.
          </Empty>
        ) : (
          [...batch.proposed, ...batch.rejected].map((c) => (
            <details className="candidate" key={c.id}>
              <summary>
                <Tag
                  tone={
                    result?.result.selected_candidate_ids.includes(c.id)
                      ? "success"
                      : ""
                  }
                >
                  {result?.result.selected_candidate_ids.includes(c.id)
                    ? "SELECTED"
                    : c.status.toUpperCase()}
                </Tag>
                <code>
                  {c.definition.table_name} (
                  {c.definition.keys.map((k) => k.column).join(", ")})
                </code>
              </summary>
              <p>
                {c.rejection_reason ??
                  result?.result.candidates.find((v) => v.candidate_id === c.id)
                    ?.reason ??
                  "Not evaluated in this saved run."}
              </p>
              {c.evidence.map((e, i) => (
                <p key={i}>{e.explanation}</p>
              ))}
              <Warnings items={c.warnings ?? []} />
              <pre>{c.definition.ddl}</pre>
            </details>
          ))
        )}
      </Panel>
    </>
  );
}
