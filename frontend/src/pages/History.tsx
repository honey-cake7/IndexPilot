import { useState, type FormEvent } from "react";
import { useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { api, type Model } from "../api/client";
import {
  Busy,
  date,
  Empty,
  ErrorBox,
  Go,
  PageTitle,
  Pager,
  Panel,
  short,
  Tag,
} from "../components/ui";

const kinds = [
  "workloads",
  "plans",
  "candidates",
  "optimizations",
  "recommendations",
  "benchmarks",
  "reports",
] as const;
const href = (r: Model<"HistoryItem">) =>
  ({
    workloads: `/queries?workload=${r.id}`,
    plans: `/queries?plan=${r.id}`,
    candidates: `/budget?batch=${r.id}`,
    optimizations: `/budget?optimization=${r.id}`,
    recommendations: `/recommendations?id=${r.id}`,
    benchmarks: `/benchmarks?job=${r.id}`,
    reports: `/reports?report=${r.id}`,
  })[r.kind];
export function History() {
  const [params, setParams] = useSearchParams();
  const kind = params.get("kind") ?? "";
  const offset = Math.max(0, Number(params.get("offset")) || 0);
  const records = useQuery({
    queryKey: ["history", params.toString()],
    queryFn: () =>
      api.history({
        kind: kinds.includes(kind as (typeof kinds)[number])
          ? (kind as (typeof kinds)[number])
          : undefined,
        q: params.get("q") ?? "",
        created_from: params.get("from") || undefined,
        created_to: params.get("to") || undefined,
        limit: 20,
        offset,
      }),
  });
  return (
    <>
      <PageTitle
        title="History"
        description="Filter saved experiments by type, title or UUID and time. Every link opens the original record."
      />
      <Panel title="Saved activity">
        <HistoryFilters
          key={params.toString()}
          params={params}
          apply={setParams}
        />
        {records.data && (
          <p className="muted small">{records.data.total} matching records</p>
        )}
        {records.isPending ? (
          <Busy />
        ) : records.isError ? (
          <ErrorBox
            error={records.error}
            retry={() => void records.refetch()}
          />
        ) : !records.data.items.length ? (
          <Empty title="No matching records">
            Change or clear the filters to find saved evidence.
          </Empty>
        ) : (
          <div className="table-wrap" tabIndex={0}>
            <table>
              <thead>
                <tr>
                  <th>Record</th>
                  <th>Identifier</th>
                  <th>Saved</th>
                  <th>Type / status</th>
                  <th>Open</th>
                </tr>
              </thead>
              <tbody>
                {records.data.items.map((r) => (
                  <tr key={`${r.kind}-${r.id}`}>
                    <td>{r.title}</td>
                    <td className="mono">{short(r.id)}</td>
                    <td>{date(r.created_at)}</td>
                    <td>
                      <Tag>{r.kind}</Tag>
                      {r.status && ` / ${r.status}`}
                    </td>
                    <td>
                      <Go to={href(r)}>View</Go>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pager
          offset={offset}
          count={records.data?.items.length ?? 0}
          total={records.data?.total}
          onChange={(n) =>
            setParams({ ...Object.fromEntries(params), offset: String(n) })
          }
        />
      </Panel>
    </>
  );
}
function localDate(value: string | null) {
  if (!value) return "";
  const d = new Date(value);
  if (!Number.isFinite(d.getTime())) return "";
  return new Date(d.getTime() - d.getTimezoneOffset() * 60000)
    .toISOString()
    .slice(0, 16);
}
function HistoryFilters({
  params,
  apply,
}: {
  params: URLSearchParams;
  apply: (p: Record<string, string>) => void;
}) {
  const [kind, setKind] = useState(params.get("kind") ?? "");
  const [q, setQ] = useState(params.get("q") ?? "");
  const [from, setFrom] = useState(localDate(params.get("from")));
  const [to, setTo] = useState(localDate(params.get("to")));
  const [error, setError] = useState<Error | null>(null);
  function submit(e: FormEvent) {
    e.preventDefault();
    if (from && to && from > to) {
      setError(new Error("Saved-from must be earlier than saved-to."));
      return;
    }
    setError(null);
    apply({
      ...(kind ? { kind } : {}),
      ...(q ? { q } : {}),
      ...(from ? { from: new Date(from).toISOString() } : {}),
      ...(to ? { to: new Date(to).toISOString() } : {}),
    });
  }
  return (
    <form onSubmit={submit}>
      <div className="field-grid">
        <label>
          Record type
          <select value={kind} onChange={(e) => setKind(e.target.value)}>
            <option value="">All record types</option>
            {kinds.map((k) => (
              <option key={k} value={k}>
                {k[0].toUpperCase() + k.slice(1)}
              </option>
            ))}
          </select>
        </label>
        <label>
          Search title or UUID
          <input
            maxLength={120}
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
        </label>
        <label>
          Saved from (local time)
          <input
            type="datetime-local"
            value={from}
            onChange={(e) => setFrom(e.target.value)}
          />
        </label>
        <label>
          Saved to (local time)
          <input
            type="datetime-local"
            value={to}
            onChange={(e) => setTo(e.target.value)}
          />
        </label>
      </div>
      <div className="actions">
        <button className="primary" type="submit">
          Apply history filters
        </button>
        <button className="secondary" type="button" onClick={() => apply({})}>
          Clear filters
        </button>
      </div>
      <ErrorBox error={error} />
    </form>
  );
}
