import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api } from "../api/client";
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
} from "../components/ui";

const sources = {
  workloads: async (offset: number) =>
    (await api.workloads(offset)).map((r) => ({
      id: r.id,
      name: r.name,
      time: r.created_at,
      detail: r.source,
      href: `/queries?workload=${r.id}`,
    })),
  plans: async (offset: number) =>
    (await api.plans(offset)).map((r) => ({
      id: r.id,
      name: r.root_node_type,
      time: r.captured_at,
      detail: "Planner estimate",
      href: `/queries?plan=${r.id}`,
    })),
  candidates: async (offset: number) =>
    (await api.batches(offset)).map((r) => ({
      id: r.id,
      name: "Candidate batch",
      time: r.created_at,
      detail: r.search_truncated ? "Bounded / truncated" : "Generated",
      href: `/budget?batch=${r.id}`,
    })),
  optimizations: async (offset: number) =>
    (await api.optimizations(offset)).map((r) => ({
      id: r.id,
      name: "Optimizer run",
      time: r.created_at,
      detail: "Saved budget and search trace",
      href: `/budget?optimization=${r.id}`,
    })),
  recommendations: async (offset: number) =>
    (await api.recommendations(offset)).map((r) => ({
      id: r.id,
      name: "Recommendation",
      time: r.created_at,
      detail: `${r.selected_count} selected indexes`,
      href: `/recommendations?id=${r.id}`,
    })),
  benchmarks: async (offset: number) =>
    (await api.benchmarks(offset)).map((r) => ({
      id: r.id,
      name: "Physical benchmark",
      time: r.created_at,
      detail: r.status,
      href: `/benchmarks?job=${r.id}`,
    })),
};
export function History() {
  const [kind, setKind] = useState<keyof typeof sources>("workloads");
  const [offset, setOffset] = useState(0);
  const records = useQuery({
    queryKey: ["history", kind, offset],
    queryFn: () => sources[kind](offset),
  });
  return (
    <>
      <PageTitle
        title="History"
        description="Return to saved evidence. New budgets create new runs; older records remain available."
      />
      <Panel title="Saved activity">
        <label>
          Record type
          <select
            value={kind}
            onChange={(e) => {
              setKind(e.target.value as keyof typeof sources);
              setOffset(0);
            }}
          >
            {Object.keys(sources).map((k) => (
              <option value={k} key={k}>
                {k[0].toUpperCase() + k.slice(1)}
              </option>
            ))}
          </select>
        </label>
        {records.isPending ? (
          <Busy />
        ) : records.isError ? (
          <ErrorBox
            error={records.error}
            retry={() => void records.refetch()}
          />
        ) : !records.data.length ? (
          <Empty title="No records on this page" />
        ) : (
          <div className="table-wrap" tabIndex={0}>
            <table>
              <thead>
                <tr>
                  <th>Record</th>
                  <th>Identifier</th>
                  <th>Saved</th>
                  <th>Evidence</th>
                  <th>Open</th>
                </tr>
              </thead>
              <tbody>
                {records.data.map((r) => (
                  <tr key={r.id}>
                    <td>{r.name}</td>
                    <td className="mono">{short(r.id)}</td>
                    <td>{date(r.time)}</td>
                    <td>{r.detail}</td>
                    <td>
                      <Go to={r.href}>View</Go>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        <Pager
          offset={offset}
          count={records.data?.length ?? 0}
          onChange={setOffset}
        />
      </Panel>
    </>
  );
}
