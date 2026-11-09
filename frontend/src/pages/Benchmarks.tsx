import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FlaskConical } from "lucide-react";
import { api, number, object, type Model } from "../api/client";
import { MeasuredChart } from "../components/Charts";
import {
  Busy,
  bytes,
  date,
  Empty,
  ErrorBox,
  fmt,
  Go,
  Json,
  PageTitle,
  Pager,
  Panel,
  short,
  Tag,
  Warnings,
} from "../components/ui";

export function Benchmarks() {
  const [params, setParams] = useSearchParams();
  const [offset, setOffset] = useState(0);
  const id = params.get("job") ?? "";
  const recommendation = params.get("recommendation") ?? "";
  const jobs = useQuery({
    queryKey: ["benchmarks", offset, recommendation],
    queryFn: () => api.benchmarks(offset, recommendation || undefined),
    refetchInterval: (q) =>
      q.state.data?.some((j) => ["queued", "running"].includes(j.status))
        ? 2000
        : false,
  });
  return (
    <>
      <PageTitle
        title="Benchmark Comparison"
        description="Compare baseline, per-query indexes and the selected set using actual pgbench measurements."
      />
      <div className="two-columns">
        <Panel title="A deliberate, isolated experiment">
          <p>
            Physical indexes and writes are created only inside worker-owned
            schemas in <code>indexpilot_bench</code>.
          </p>
          <p className="muted small">
            Queueing does not start a worker. Run this command in a separate
            terminal from the repository root:
          </p>
          <pre>uv run python scripts/run_benchmarks.py --serve</pre>
          <p className="muted small">
            Repetitions rotate the three arms. Read and write phases have
            different transaction definitions. Results depend on this machine
            and warm-cache conditions.
          </p>
          <Go to="/reports">Download saved evidence</Go>
        </Panel>
        <BenchmarkForm
          key={recommendation}
          recommendation={recommendation}
          onQueued={(job) => setParams({ job: job.id })}
        />
      </div>
      <div className="explorer-layout">
        <Panel title="Saved benchmark jobs">
          {jobs.isPending ? (
            <Busy />
          ) : jobs.isError ? (
            <ErrorBox error={jobs.error} />
          ) : !jobs.data.length ? (
            <Empty title="No saved jobs on this page">
              Choose a saved recommendation and confirm an isolated benchmark.
            </Empty>
          ) : (
            <div className="record-list">
              {jobs.data.map((j) => (
                <button
                  key={j.id}
                  className={j.id === id ? "selected" : ""}
                  onClick={() => setParams({ job: j.id })}
                >
                  <strong>
                    {short(j.id)}{" "}
                    <Tag
                      tone={
                        j.status === "completed"
                          ? "success"
                          : j.status === "failed"
                            ? "warning"
                            : ""
                      }
                    >
                      {j.status}
                    </Tag>
                  </strong>
                  <small>{date(j.created_at)}</small>
                </button>
              ))}
            </div>
          )}
          <Pager
            offset={offset}
            count={jobs.data?.length ?? 0}
            onChange={setOffset}
          />
        </Panel>
        {id ? (
          <BenchmarkDetail key={id} id={id} />
        ) : (
          <Panel>
            <Empty title="Choose a measured experiment">
              A job’s saved status, conditions, storage and regressions appear
              here.
            </Empty>
          </Panel>
        )}
      </div>
    </>
  );
}
export function BenchmarkForm({
  recommendation,
  onQueued,
}: {
  recommendation: string;
  onQueued: (job: Model<"BenchmarkView">) => void;
}) {
  const [rec, setRec] = useState(recommendation);
  const [offset, setOffset] = useState(0);
  const [confirmed, setConfirmed] = useState(false);
  const [fields, setFields] = useState({
    orders: "10000",
    seed: "42",
    repetitions: "3",
    clients: "1",
    transactions_per_client: "200",
    read_warmup_per_client: "20",
    timeout_seconds: "300",
    regression_threshold_pct: "10",
  });
  const recs = useQuery({
    queryKey: ["recommendations", offset],
    queryFn: () => api.recommendations(offset),
  });
  const qc = useQueryClient();
  const enqueue = useMutation({
    mutationFn: () => {
      if (!confirmed)
        throw new Error(
          "Explicit confirmation is required for physical benchmarking.",
        );
      return api.enqueue({
        recommendation_id: rec,
        confirm_disposable_benchmark: true,
        orders: Number(fields.orders),
        seed: Number(fields.seed),
        repetitions: Number(fields.repetitions),
        clients: Number(fields.clients),
        transactions_per_client: Number(fields.transactions_per_client),
        read_warmup_per_client: Number(fields.read_warmup_per_client),
        timeout_seconds: Number(fields.timeout_seconds),
        regression_threshold_pct: Number(fields.regression_threshold_pct),
      });
    },
    onSuccess: (data) => {
      setConfirmed(false);
      void qc.invalidateQueries({ queryKey: ["benchmarks"] });
      void qc.invalidateQueries({ queryKey: ["overview"] });
      onQueued(data);
    },
  });
  const definitions = [
    ["orders", "Order rows", 1000, 100000],
    ["seed", "Dataset seed", 0, 2147483647],
    ["repetitions", "Repetitions", 1, 5],
    ["clients", "Clients", 1, 4],
    ["transactions_per_client", "Transactions per client / phase", 5, 10000],
    ["read_warmup_per_client", "Read warmup per client", 0, 1000],
    ["timeout_seconds", "Job timeout (seconds)", 10, 600],
    ["regression_threshold_pct", "Regression threshold (%)", 0, 1000],
  ] as const;
  function submit(e: FormEvent) {
    e.preventDefault();
    enqueue.mutate();
  }
  return (
    <Panel title="Queue a benchmark">
      <form onSubmit={submit}>
        <fieldset disabled={enqueue.isPending}>
          <label>
            Recommendation
            <select
              required
              value={rec}
              onChange={(e) => {
                setRec(e.target.value);
                setConfirmed(false);
              }}
            >
              <option value="">Choose a saved recommendation</option>
              {rec && !recs.data?.some((r) => r.id === rec) && (
                <option value={rec}>{short(rec)} · selected record</option>
              )}
              {recs.data?.map((r) => (
                <option key={r.id} value={r.id}>
                  {short(r.id)} · {r.selected_count} indexes
                </option>
              ))}
            </select>
          </label>
          <ErrorBox error={recs.error} />
          <Pager
            offset={offset}
            count={recs.data?.length ?? 0}
            onChange={setOffset}
          />
          <details>
            <summary>Dataset & measurement settings</summary>
            <div className="field-grid">
              {definitions.map(([key, label, min, max]) => (
                <label key={key}>
                  {label}
                  <input
                    required
                    type="number"
                    min={min}
                    max={max}
                    step={key === "regression_threshold_pct" ? "any" : "1"}
                    value={fields[key]}
                    onChange={(e) => {
                      setFields({ ...fields, [key]: e.target.value });
                      setConfirmed(false);
                    }}
                  />
                </label>
              ))}
            </div>
          </details>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => setConfirmed(e.target.checked)}
            />
            I confirm physical indexes and writes in the disposable
            indexpilot_bench database.
          </label>
          <button
            className="primary"
            type="submit"
            disabled={!confirmed || !rec}
          >
            <FlaskConical size={16} />
            {enqueue.isPending ? "Queueing…" : "Queue confirmed benchmark"}
          </button>
        </fieldset>
      </form>
      <ErrorBox error={enqueue.error} />
    </Panel>
  );
}
function BenchmarkDetail({ id }: { id: string }) {
  const [phase, setPhase] = useState("read_mix");
  const qc = useQueryClient();
  const job = useQuery({
    queryKey: ["benchmark", id],
    queryFn: () => api.benchmark(id),
    refetchInterval: (q) =>
      q.state.data && ["queued", "running"].includes(q.state.data.status)
        ? 2000
        : false,
  });
  const measurements = useQuery({
    queryKey: ["measurements", id],
    queryFn: () => api.measurements(id),
    refetchInterval: () =>
      job.data && ["queued", "running"].includes(job.data.status)
        ? 2000
        : false,
  });
  const cancel = useMutation({
    mutationFn: () => api.cancel(id),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ["benchmark", id] });
      void qc.invalidateQueries({ queryKey: ["benchmarks"] });
    },
  });
  if (job.isPending) return <Busy />;
  if (job.isError) return <ErrorBox error={job.error} />;
  const d = job.data;
  const phases = [...new Set(measurements.data?.map((m) => m.phase) ?? [])];
  const result = object(d.result);
  const warnings = Array.isArray(result.warnings)
    ? result.warnings.filter((w): w is string => typeof w === "string")
    : [];
  const comparisons = Array.isArray(result.comparisons)
    ? result.comparisons.map(object)
    : [];
  return (
    <div>
      <Panel title={`Experiment ${short(id)}`}>
        <div className="panel-heading">
          <Tag
            tone={
              d.status === "completed"
                ? "success"
                : d.status === "failed"
                  ? "warning"
                  : ""
            }
          >
            {d.status.toUpperCase()}
          </Tag>
          <span className="muted small">
            Cleanup {d.cleanup_confirmed ? "verified" : "unconfirmed"}
          </span>
        </div>
        <Go to={`/recommendations?id=${d.recommendation_id}`}>
          Source recommendation {short(d.recommendation_id)}
        </Go>
        {d.status !== "completed" && (
          <p className="notice">
            {d.status === "queued"
              ? "Queued. Start the explicit benchmark worker to execute this job."
              : d.status === "running"
                ? "Running. Measurements shown so far are partial."
                : `This job ${d.status}. Partial measurements do not establish a completed comparison.`}
          </p>
        )}
        {d.error_code && (
          <p role="alert" className="notice error">
            Worker result: {d.error_code}
          </p>
        )}
        {["queued", "running"].includes(d.status) && (
          <button
            className="secondary"
            disabled={cancel.isPending || d.cancel_requested}
            onClick={() => cancel.mutate()}
          >
            {d.cancel_requested
              ? "Cancellation requested"
              : "Request cancellation"}
          </button>
        )}
        <ErrorBox error={cancel.error} />
        {measurements.isPending ? (
          <Busy />
        ) : measurements.isError ? (
          <ErrorBox error={measurements.error} />
        ) : (
          <>
            <label>
              Measured phase
              <select value={phase} onChange={(e) => setPhase(e.target.value)}>
                {!phases.includes("read_mix") && (
                  <option value="read_mix">read_mix (no samples)</option>
                )}
                {phases.map((p) => (
                  <option key={p}>{p}</option>
                ))}
              </select>
            </label>
            <MeasuredChart measurements={measurements.data} phase={phase} />
            {comparisons
              .filter((c) => c.phase === phase)
              .map((c, i) => (
                <p className={c.regression ? "notice error" : "notice"} key={i}>
                  {String(c.arm)}: {fmt(number(c.measured_improvement_pct))}%
                  measured mean improvement
                  {c.regression ? " · REGRESSION FLAG" : ""}. Repetition
                  standard deviation {fmt(number(c.repetition_stddev_ms), 4)}{" "}
                  ms.
                </p>
              ))}
            <details>
              <summary>Storage & measurement conditions</summary>
              <div className="table-wrap" tabIndex={0}>
                <table>
                  <thead>
                    <tr>
                      <th>Arm / repetition</th>
                      <th>Samples</th>
                      <th>Throughput</th>
                      <th>Additional initial index bytes</th>
                      <th>Initial budget fit</th>
                    </tr>
                  </thead>
                  <tbody>
                    {measurements.data
                      .filter((m) => m.phase === phase)
                      .map((m) => (
                        <tr key={m.id}>
                          <td>
                            {m.arm} / {m.repetition}
                          </td>
                          <td>{fmt(number(m.metrics.samples), 0)}</td>
                          <td>{fmt(number(m.metrics.tps))} tx/s</td>
                          <td>
                            {bytes(number(m.conditions.additional_index_bytes))}
                          </td>
                          <td>
                            {m.conditions.actual_budget_fit == null
                              ? "Unknown"
                              : m.conditions.actual_budget_fit
                                ? "Yes"
                                : "No"}
                          </td>
                        </tr>
                      ))}
                  </tbody>
                </table>
              </div>
              <p className="muted small">
                Storage is additional main-fork index bytes at phase start.
                Actual write-phase growth, fingerprints, transaction
                definitions, sample method and timestamps remain in the evidence
                JSON.
              </p>
              <Json value={measurements.data} />
            </details>
          </>
        )}
        <Warnings items={warnings} />
        <Json title="Saved request, manifest and result" value={d} />
      </Panel>
    </div>
  );
}
