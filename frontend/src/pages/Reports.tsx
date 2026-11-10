import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Download, Save } from "lucide-react";
import { api, type Model } from "../api/client";
import {
  Busy,
  bytes,
  date,
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

export function Reports() {
  const [params, setParams] = useSearchParams();
  const [sourceOffset, setSourceOffset] = useState(0);
  const [offset, setOffset] = useState(0);
  const [search, setSearch] = useState("");
  const [query, setQuery] = useState("");
  const source = params.get("id") ?? "";
  const id = params.get("report") ?? "";
  const compare = params.get("compare") ?? "";
  const recs = useQuery({
    queryKey: ["recommendations", sourceOffset],
    queryFn: () => api.recommendations(sourceOffset),
  });
  const list = useQuery({
    queryKey: ["reports", offset, query, source],
    queryFn: () => api.reports(offset, query, source || undefined),
  });
  const report = useQuery({
    queryKey: ["report", id],
    queryFn: () => api.report(id),
    enabled: !!id,
  });
  const other = useQuery({
    queryKey: ["report", compare],
    queryFn: () => api.report(compare),
    enabled: !!compare,
  });
  function setRecord(report: string) {
    setParams({ ...Object.fromEntries(params), report });
  }
  return (
    <>
      <PageTitle
        title="Reports"
        description="Save versioned evidence, compare past decisions, and download reproducible JSON or Markdown."
      />
      <Panel title="Create a frozen report">
        <label>
          Source recommendation
          <select
            value={source}
            onChange={(e) => {
              setParams({ id: e.target.value });
              setOffset(0);
            }}
          >
            <option value="">Choose a saved recommendation</option>
            {source && !recs.data?.some((r) => r.id === source) && (
              <option value={source}>{short(source)} · selected record</option>
            )}
            {recs.data?.map((r) => (
              <option key={r.id} value={r.id}>
                {short(r.id)} · {r.selected_count} indexes ·{" "}
                {date(r.created_at)}
              </option>
            ))}
          </select>
        </label>
        <ErrorBox error={recs.error} />
        <Pager
          offset={sourceOffset}
          count={recs.data?.length ?? 0}
          onChange={setSourceOffset}
        />
        {source && (
          <ReportForm
            key={source}
            source={source}
            onCreated={(data) => setRecord(data.id)}
          />
        )}
      </Panel>
      <div className="explorer-layout">
        <Panel title="Saved reports">
          <form
            onSubmit={(e) => {
              e.preventDefault();
              setQuery(search);
              setOffset(0);
            }}
          >
            <label>
              Search report title
              <input
                value={search}
                maxLength={120}
                onChange={(e) => setSearch(e.target.value)}
              />
            </label>
            <button className="secondary" type="submit">
              Search reports
            </button>
          </form>
          <p className="muted small">
            {source
              ? "Filtered to the source recommendation."
              : "All recommendations."}{" "}
            {list.data ? `${list.data.total} saved reports` : ""}
          </p>
          {list.isPending ? (
            <Busy />
          ) : list.isError ? (
            <ErrorBox error={list.error} />
          ) : !list.data.items.length ? (
            <Empty title="No reports on this page">
              Create a report from a saved recommendation, or change the search.
            </Empty>
          ) : (
            <div className="record-list">
              {list.data.items.map((r) => (
                <button
                  key={r.id}
                  className={id === r.id ? "selected" : ""}
                  onClick={() => setRecord(r.id)}
                >
                  <strong>{r.title}</strong>
                  <small>
                    {short(r.id)} · {date(r.created_at)}
                  </small>
                </button>
              ))}
            </div>
          )}
          <Pager
            offset={offset}
            count={list.data?.items.length ?? 0}
            total={list.data?.total}
            onChange={setOffset}
          />
        </Panel>
        <div>
          {!id ? (
            <Panel>
              <Empty title="Choose a saved report">
                Reports retain the evidence and privacy policy captured at
                creation.
              </Empty>
            </Panel>
          ) : report.isPending ? (
            <Busy />
          ) : report.isError ? (
            <ErrorBox error={report.error} />
          ) : (
            <>
              <ReportDetail report={report.data} />
              <Panel title="Compare saved reports">
                <label>
                  Compare with another report
                  <select
                    value={compare}
                    onChange={(e) =>
                      setParams({
                        ...Object.fromEntries(params),
                        compare: e.target.value,
                      })
                    }
                  >
                    <option value="">Choose a report from this list</option>
                    {compare &&
                      !list.data?.items.some((r) => r.id === compare) && (
                        <option value={compare}>
                          {short(compare)} · selected record
                        </option>
                      )}
                    {list.data?.items
                      .filter((r) => r.id !== id)
                      .map((r) => (
                        <option key={r.id} value={r.id}>
                          {r.title} · {short(r.id)}
                        </option>
                      ))}
                  </select>
                </label>
                <p className="muted small">
                  Browse report pages or clear the source filter to choose
                  another saved record.
                </p>
                {other.isPending && compare ? (
                  <Busy />
                ) : other.isError ? (
                  <ErrorBox error={other.error} />
                ) : (
                  other.data && (
                    <ReportComparison left={report.data} right={other.data} />
                  )
                )}
              </Panel>
            </>
          )}
        </div>
      </div>
    </>
  );
}

function ReportForm({
  source,
  onCreated,
}: {
  source: string;
  onCreated: (report: Model<"ReportDocument">) => void;
}) {
  const [title, setTitle] = useState("Optimization report");
  const [original, setOriginal] = useState(true);
  const [representative, setRepresentative] = useState(false);
  const [selected, setSelected] = useState<string[]>([]);
  const [offset, setOffset] = useState(0);
  const qc = useQueryClient();
  const jobs = useQuery({
    queryKey: ["report-jobs", source, offset],
    queryFn: () => api.benchmarks(offset, source),
  });
  const create = useMutation({
    mutationFn: () =>
      api.createReport({
        recommendation_id: source,
        title,
        benchmark_ids: selected,
        include_original_sql: original,
        include_representative_sql: representative,
      }),
    onSuccess: (data) => {
      qc.setQueryData(["report", data.id], data);
      void qc.invalidateQueries({ queryKey: ["reports"] });
      void qc.invalidateQueries({ queryKey: ["history"] });
      onCreated(data);
    },
  });
  function submit(e: FormEvent) {
    e.preventDefault();
    create.mutate();
  }
  return (
    <form onSubmit={submit}>
      <fieldset disabled={create.isPending}>
        <label>
          Report title
          <input
            required
            value={title}
            maxLength={120}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <div className="field-grid">
          <label className="checkbox">
            <input
              type="checkbox"
              checked={original}
              onChange={(e) => {
                setOriginal(e.target.checked);
                if (!e.target.checked) setRepresentative(false);
              }}
            />
            Include original SQL and deployment SQL. Original SQL may contain
            literal values.
          </label>
          <label className="checkbox">
            <input
              type="checkbox"
              checked={representative}
              disabled={!original}
              onChange={(e) => setRepresentative(e.target.checked)}
            />
            Include representative SQL with bound parameter values.
          </label>
        </div>
        <p className="muted small">
          Typed parameter maps and raw plans are omitted. The saved policy
          states what was included.
        </p>
        <details>
          <summary>
            Choose benchmark evidence ({selected.length}/5 selected)
          </summary>
          {jobs.isPending ? (
            <Busy />
          ) : jobs.isError ? (
            <ErrorBox error={jobs.error} />
          ) : !jobs.data.length ? (
            <p className="muted">
              No benchmark jobs on this page. The report will explicitly
              identify missing measurements.
            </p>
          ) : (
            jobs.data.map((j) => (
              <label className="checkbox" key={j.id}>
                <input
                  type="checkbox"
                  checked={selected.includes(j.id)}
                  disabled={
                    ["queued", "running"].includes(j.status) ||
                    (!selected.includes(j.id) && selected.length >= 5)
                  }
                  onChange={(e) =>
                    setSelected(
                      e.target.checked
                        ? [...selected, j.id]
                        : selected.filter((id) => id !== j.id),
                    )
                  }
                />
                Include benchmark {short(j.id)} ({j.status}; cleanup{" "}
                {j.cleanup_confirmed ? "verified" : "unconfirmed"})
              </label>
            ))
          )}
          <Pager
            offset={offset}
            count={jobs.data?.length ?? 0}
            onChange={setOffset}
          />
        </details>
        <button className="primary" type="submit">
          <Save size={16} />
          {create.isPending ? "Saving report…" : "Save versioned report"}
        </button>
      </fieldset>
      <ErrorBox error={create.error} />
    </form>
  );
}

export function ReportDetail({
  report: r,
}: {
  report: Model<"ReportDocument">;
}) {
  return (
    <>
      <Panel title={r.title}>
        <div className="panel-heading">
          <Tag>{r.format_version}</Tag>
          <code>{short(r.id)}</code>
        </div>
        <p className="muted small">Frozen {date(r.created_at)}</p>
        <div className="actions">
          <a
            className="primary"
            href={`/api/v1/reports/${r.id}/download.json`}
            download
          >
            <Download size={16} />
            Download report JSON
          </a>
          <a
            className="secondary"
            href={`/api/v1/reports/${r.id}/download.md`}
            download
          >
            <Download size={16} />
            Download report Markdown
          </a>
        </div>
        <div className="metrics compact">
          <Metric
            label="Saved budget"
            value={bytes(r.summary.storage_budget_bytes)}
            note="Estimated-byte constraint"
          />
          <Metric
            label="Selected size"
            value={bytes(r.summary.estimated_size_bytes)}
            note={`${r.indexes.length} selected indexes`}
          />
          <Metric
            label="Read improvement"
            value={
              r.summary.estimated_read_improvement_pct === null
                ? "Unknown"
                : `${fmt(r.summary.estimated_read_improvement_pct)}%`
            }
            note="Planner estimate, not latency"
          />
        </div>
        <Go to={`/recommendations?id=${r.recommendation_id}`}>
          Source recommendation {short(r.recommendation_id)}
        </Go>
        <p className="muted small">{r.policy.parameter_policy}</p>
        <Json
          title="Saved settings and provenance"
          value={{ settings: r.settings, provenance: r.provenance }}
        />
      </Panel>
      <Panel title="Missing evidence & limitations">
        <ul className="plain-steps">
          {r.missing_evidence.map((m, i) => (
            <li key={i}>{m}</li>
          ))}
        </ul>
      </Panel>
      <Panel title="Candidate decisions">
        <div className="table-wrap" tabIndex={0}>
          <table>
            <thead>
              <tr>
                <th>Candidate</th>
                <th>Selection</th>
                <th>Reason</th>
              </tr>
            </thead>
            <tbody>
              {r.candidates.map((c) => (
                <tr key={c.candidate_id}>
                  <td className="mono">
                    {c.schema_name}.{c.table_name} (
                    {c.keys.map((k) => k.column).join(", ")})
                  </td>
                  <td>
                    <Tag tone={c.selected ? "success" : ""}>
                      {c.selected
                        ? "Selected"
                        : c.generation_status === "rejected"
                          ? "Rejected at generation"
                          : "Not selected"}
                    </Tag>
                  </td>
                  <td>{c.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Panel>
      <Panel title="Selected index explanations">
        {!r.indexes.length ? (
          <p className="muted">Empty selection: no indexes were selected.</p>
        ) : (
          r.indexes.map((index) => (
            <details key={index.candidate_id}>
              <summary>
                {index.index_name} · {bytes(index.estimated_size_bytes)}
              </summary>
              <p>{index.explanation.selection_reason}</p>
              <p className="muted small">{index.explanation.write_overhead}</p>
              {index.deployment_sql !== null && (
                <>
                  <p className="small">Deployment SQL for human review only</p>
                  <pre>{index.deployment_sql}</pre>
                </>
              )}
              <Warnings items={index.explanation.warnings} />
            </details>
          ))
        )}
      </Panel>
      <Panel title="Query evidence">
        {r.queries.map((q, i) => (
          <details key={q.source_plan_id}>
            <summary>
              Query {i + 1} · frequency {fmt(q.frequency)} · cost{" "}
              {fmt(q.explanation.baseline_cost)} →{" "}
              {fmt(q.explanation.final_cost)}
            </summary>
            {q.original_sql === null ? (
              <p>Original SQL omitted by policy.</p>
            ) : (
              <pre>{q.original_sql}</pre>
            )}
            {q.representative_sql !== null && <pre>{q.representative_sql}</pre>}
            <Json
              title="Saved query costs and statistics"
              value={{ explanation: q.explanation, statistics: q.statistics }}
            />
          </details>
        ))}
      </Panel>
      <Panel title="Frozen benchmark evidence">
        {!r.benchmarks.length ? (
          <p className="muted">
            No benchmark was selected. Planner costs do not establish measured
            performance.
          </p>
        ) : (
          r.benchmarks.map((b) => (
            <article className="index-card" key={b.id}>
              <Go to={`/benchmarks?job=${b.id}`}>Benchmark {short(b.id)}</Go>
              <p>
                {b.status} · cleanup{" "}
                {b.cleanup_confirmed ? "verified" : "unconfirmed"} ·{" "}
                {b.measurements.length} recorded measurements
              </p>
              {!b.complete_comparison && (
                <p className="notice">
                  Partial evidence; no completed comparison is claimed.
                </p>
              )}
              <Json
                title="Frozen conditions, measurements and regression flags"
                value={b}
              />
            </article>
          ))
        )}
      </Panel>
      <Panel title="Complete report">
        <Warnings items={r.warnings} />
        <Json value={r} />
      </Panel>
    </>
  );
}

function ReportComparison({
  left,
  right,
}: {
  left: Model<"ReportDocument">;
  right: Model<"ReportDocument">;
}) {
  const same = left.batch_id === right.batch_id;
  return (
    <>
      <p className="notice">
        {same
          ? "These reports refer to the same candidate batch. Check captured settings and selected benchmark conditions before comparing."
          : "Different candidate batches: workloads or source conditions may differ. A direct performance improvement cannot be inferred."}
      </p>
      <div className="table-wrap" tabIndex={0}>
        <table>
          <thead>
            <tr>
              <th>Saved evidence</th>
              <th>{left.title}</th>
              <th>{right.title}</th>
            </tr>
          </thead>
          <tbody>
            <tr>
              <td>Report ID</td>
              <td>{short(left.id)}</td>
              <td>{short(right.id)}</td>
            </tr>
            <tr>
              <td>Storage budget</td>
              <td>{bytes(left.settings.storage_budget_bytes)}</td>
              <td>{bytes(right.settings.storage_budget_bytes)}</td>
            </tr>
            <tr>
              <td>Selected estimated bytes</td>
              <td>{bytes(left.summary.estimated_size_bytes)}</td>
              <td>{bytes(right.summary.estimated_size_bytes)}</td>
            </tr>
            <tr>
              <td>Final weighted root cost</td>
              <td>{fmt(left.summary.final_score.read_cost)}</td>
              <td>{fmt(right.summary.final_score.read_cost)}</td>
            </tr>
            <tr>
              <td>Selected indexes</td>
              <td>{left.indexes.length}</td>
              <td>{right.indexes.length}</td>
            </tr>
            <tr>
              <td>Complete measured comparisons</td>
              <td>
                {left.benchmarks.filter((b) => b.complete_comparison).length}
              </td>
              <td>
                {right.benchmarks.filter((b) => b.complete_comparison).length}
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </>
  );
}
