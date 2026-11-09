import { useState } from "react";
import { useSearchParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, type Model } from "../api/client";
import {
  Busy,
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

export function PlanTree({
  node,
  depth = 0,
}: {
  node: Model<"PlanNode">;
  depth?: number;
}) {
  return (
    <details className="plan-node" open={depth < 2}>
      <summary>
        <strong>{node.node_type}</strong>
        {node.relation_name && (
          <code>
            {node.schema_name}.{node.relation_name}
          </code>
        )}
        <span>
          cost {fmt(node.total_cost)} · rows {fmt(node.estimated_rows, 0)}
        </span>
      </summary>
      <div className="node-body">
        {node.index_name && (
          <p>
            Index: <code>{node.index_name}</code>
          </p>
        )}
        {[
          node.index_condition,
          node.recheck_condition,
          node.filter_condition,
          ...Object.values(node.join_conditions ?? {}),
        ]
          .filter(Boolean)
          .map((c, i) => (
            <pre key={i}>{c}</pre>
          ))}
        {(node.sort_keys ?? []).length > 0 && (
          <p>Sort: {(node.sort_keys ?? []).join(", ")}</p>
        )}
        {(node.children ?? []).map((child, i) => (
          <PlanTree node={child} key={i} depth={depth + 1} />
        ))}
      </div>
    </details>
  );
}
export function Explorer() {
  const [params, setParams] = useSearchParams();
  const [offset, setOffset] = useState(0);
  const [patternOffset, setPatternOffset] = useState(0);
  const kind =
    params.has("workload") || params.get("tab") === "workloads"
      ? "workloads"
      : "plans";
  const id = params.get(kind === "plans" ? "plan" : "workload") ?? "";
  const plans = useQuery({
    queryKey: ["plans", offset],
    queryFn: () => api.plans(offset),
    enabled: kind === "plans",
  });
  const workloads = useQuery({
    queryKey: ["workloads", offset],
    queryFn: () => api.workloads(offset),
    enabled: kind === "workloads",
  });
  const plan = useQuery({
    queryKey: ["plan", id],
    queryFn: () => api.plan(id),
    enabled: kind === "plans" && !!id,
  });
  const workload = useQuery({
    queryKey: ["workload", id, patternOffset],
    queryFn: () => api.workload(id, patternOffset),
    enabled: kind === "workloads" && !!id,
  });
  const qc = useQueryClient();
  const capture = useMutation({
    mutationFn: api.planScenario,
    onSuccess: (data) => {
      void qc.invalidateQueries();
      setParams({ plan: data.id });
    },
  });
  const list = kind === "plans" ? plans : workloads;
  return (
    <>
      <PageTitle
        title="Query Explorer"
        description="Inspect saved SQL, representative scenarios and recursive PostgreSQL plans."
      />
      <div className="segmented" role="group" aria-label="Explore">
        <button
          className={kind === "plans" ? "active" : ""}
          aria-pressed={kind === "plans"}
          onClick={() => {
            setOffset(0);
            setParams({ tab: "plans" });
          }}
        >
          Plans
        </button>
        <button
          className={kind === "workloads" ? "active" : ""}
          aria-pressed={kind === "workloads"}
          onClick={() => {
            setOffset(0);
            setParams({ tab: "workloads" });
          }}
        >
          Workloads
        </button>
      </div>
      <ErrorBox error={capture.error} />
      <div className="explorer-layout">
        <Panel title={`Saved ${kind}`}>
          {list.isPending ? (
            <Busy />
          ) : list.isError ? (
            <ErrorBox error={list.error} />
          ) : !list.data?.length ? (
            <Empty />
          ) : (
            <>
              <div className="record-list">
                {kind === "plans"
                  ? plans.data?.map((p) => (
                      <button
                        key={p.id}
                        className={id === p.id ? "selected" : ""}
                        onClick={() => setParams({ plan: p.id })}
                      >
                        <strong>{p.root_node_type}</strong>
                        <span className="mono">
                          {short(p.id)} · {fmt(p.total_cost)} cost
                        </span>
                        <small>{date(p.captured_at)}</small>
                      </button>
                    ))
                  : workloads.data?.map((w) => (
                      <button
                        key={w.id}
                        className={id === w.id ? "selected" : ""}
                        onClick={() => {
                          setPatternOffset(0);
                          setParams({ workload: w.id });
                        }}
                      >
                        <strong>{w.name}</strong>
                        <small>
                          {w.source} · {date(w.created_at)}
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
              <Empty title="Choose a saved record">
                Open a plan or workload to inspect its stored evidence.
              </Empty>
            </Panel>
          ) : kind === "plans" ? (
            plan.isPending ? (
              <Busy />
            ) : plan.isError ? (
              <ErrorBox error={plan.error} />
            ) : (
              <Panel title={`Plan ${short(plan.data.id)}`}>
                <Tag>PLANNER ESTIMATE</Tag>
                <pre>{plan.data.original_sql}</pre>
                <div className="metrics compact">
                  <Metric
                    label="Root total cost"
                    value={fmt(plan.data.plan.root.total_cost)}
                    note="Planner cost units"
                  />
                  <Metric
                    label="Frequency"
                    value={fmt(plan.data.frequency)}
                    note="Saved scenario weight"
                  />
                  <Metric
                    label="Plan nodes"
                    value={plan.data.plan.node_count}
                    note="Child costs overlap root cost"
                  />
                </div>
                <PlanTree node={plan.data.plan.root} />
                <Warnings
                  items={[
                    ...plan.data.plan.warnings,
                    ...plan.data.plan.observations.map((o) => o.message),
                  ]}
                />
                <Json
                  title="Canonical SQL and resolved catalog analysis"
                  value={plan.data.analysis}
                />
                <Json
                  title="Planner settings"
                  value={plan.data.planner_settings}
                />
                <Json
                  title="Original EXPLAIN JSON"
                  value={plan.data.raw_explain}
                />
              </Panel>
            )
          ) : workload.isPending ? (
            <Busy />
          ) : workload.isError ? (
            <ErrorBox error={workload.error} />
          ) : (
            <Panel title={workload.data.name}>
              <p className="muted">
                {workload.data.pattern_total} patterns · {workload.data.source}
              </p>
              <Warnings items={workload.data.warnings} />
              {workload.data.patterns.map((p) => (
                <div className="query-input" key={p.id}>
                  <pre>{p.normalized_sql}</pre>
                  {p.scenarios.map((s) => (
                    <div key={s.id}>
                      <Tag>Frequency {fmt(s.frequency)}</Tag>
                      <pre>{s.representative_sql ?? s.sql}</pre>
                      {s.missing_parameters.length ? (
                        <p className="notice">
                          Missing values for ${s.missing_parameters.join(", $")}
                          .{" "}
                          <Go to="/analyzer">
                            Enter representative parameters
                          </Go>
                        </p>
                      ) : (
                        <button
                          className="secondary"
                          disabled={capture.isPending}
                          onClick={() => capture.mutate(s.id)}
                        >
                          {capture.isPending ? "Capturing…" : "Capture plan"}
                        </button>
                      )}
                      <Json
                        title="Stored parameter scenario"
                        value={s.parameters}
                      />
                    </div>
                  ))}
                </div>
              ))}
              <Pager
                size={100}
                offset={patternOffset}
                count={workload.data.patterns.length}
                onChange={setPatternOffset}
              />
            </Panel>
          )}
        </div>
      </div>
    </>
  );
}
