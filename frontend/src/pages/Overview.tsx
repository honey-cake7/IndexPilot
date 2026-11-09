import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowUpRight, Database, Plus, ShieldCheck } from "lucide-react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api/client";
import {
  Busy,
  bytes,
  date,
  Empty,
  ErrorBox,
  fmt,
  Go,
  Metric,
  PageTitle,
  Panel,
  short,
  Tag,
  Warnings,
} from "../components/ui";
import { MeasuredChart } from "../components/Charts";

export function Overview() {
  const stats = useQuery({ queryKey: ["overview"], queryFn: api.overview });
  const recs = useQuery({
    queryKey: ["recommendations", 0],
    queryFn: () => api.recommendations(),
  });
  const jobs = useQuery({
    queryKey: ["benchmarks", 0],
    queryFn: () => api.benchmarks(),
  });
  const latest = jobs.data?.find(
    (j) => j.status === "completed" && j.cleanup_confirmed,
  );
  const measures = useQuery({
    queryKey: ["measurements", latest?.id],
    queryFn: () => api.measurements(latest!.id),
    enabled: !!latest,
  });
  return (
    <>
      <PageTitle
        title="Your workload, understood."
        description="Turn query patterns into index decisions you can explain."
        action={
          <Link className="primary" to="/analyzer">
            <Plus size={17} />
            Analyze a workload
          </Link>
        }
      />
      <div className="hero">
        <div>
          <Tag tone="dark">POSTGRESQL / LOCAL WORKSPACE</Tag>
          <h2>Make room for better queries.</h2>
          <p>
            Inspect plans. Explore index trade-offs.
            <br />
            Put your storage budget to work.
          </p>
          <Go to="/budget">Explore the budget simulator</Go>
        </div>
        <div className="hero-visual" aria-hidden="true">
          <span className="visual-caption">WORKLOAD → INDEX SET</span>
          <div className="visual-bars">
            <i />
            <i />
            <i />
            <i />
            <i />
          </div>
          <div className="visual-foot">
            <Database size={16} />
            <span>
              Hypothetical first.
              <br />
              Evidence always.
            </span>
          </div>
        </div>
      </div>
      {stats.isPending ? (
        <Busy />
      ) : stats.isError ? (
        <ErrorBox error={stats.error} retry={() => void stats.refetch()} />
      ) : (
        <div className="metrics">
          <Metric
            label="Saved workloads"
            value={fmt(stats.data.workload_count, 0)}
            note="Explicit frequencies & collected patterns"
          />
          <Metric
            label="Captured plans"
            value={fmt(stats.data.plan_count, 0)}
            note="Root cost estimates from PostgreSQL"
          />
          <Metric
            label="Recommendations"
            value={fmt(stats.data.recommendation_count, 0)}
            note="Saved, explainable index selections"
          />
          <Metric
            label="Completed benchmarks"
            value={fmt(stats.data.completed_benchmark_count, 0)}
            note={`${stats.data.active_benchmark_count} queued or running · cleanup verified`}
          />
        </div>
      )}
      <div className="two-columns">
        <Panel
          title="Measured comparison"
          action={<Go to="/benchmarks">All benchmarks</Go>}
        >
          <p className="muted small">
            Latest completed job in the 20 most recent jobs
          </p>
          {jobs.isPending ? (
            <Busy />
          ) : jobs.isError ? (
            <ErrorBox error={jobs.error} />
          ) : latest ? (
            <>
              <Tag tone="success">MEASURED · {short(latest.id)}</Tag>
              {measures.isPending ? (
                <Busy />
              ) : measures.isError ? (
                <ErrorBox error={measures.error} />
              ) : (
                <MeasuredChart measurements={measures.data} />
              )}
              <Go to={`/benchmarks?job=${latest.id}`}>
                View conditions and write results
              </Go>
            </>
          ) : (
            <Empty title="Measurement starts with an experiment">
              A confirmed benchmark records latency independently of planner
              estimates.
            </Empty>
          )}
        </Panel>
        <Panel title="How a recommendation happens">
          <ol className="steps">
            <li>
              <span>01</span>
              <div>
                <strong>Bring the workload</strong>
                <p>SQL, representative values and how often each query runs.</p>
              </div>
            </li>
            <li>
              <span>02</span>
              <div>
                <strong>Explore the trade-offs</strong>
                <p>
                  Real HypoPG estimates, interacting indexes and a hard size
                  budget.
                </p>
              </div>
            </li>
            <li>
              <span>03</span>
              <div>
                <strong>Check the evidence</strong>
                <p>Review reasons. Measure reads and writes in isolation.</p>
              </div>
            </li>
          </ol>
          <div className="info-line">
            <ShieldCheck size={18} />
            <p>
              Ordinary analysis never deploys a physical index on your monitored
              database.
            </p>
          </div>
        </Panel>
      </div>
      <Panel
        title="Recent recommendations"
        action={<Go to="/recommendations">View history</Go>}
      >
        {recs.isPending ? (
          <Busy />
        ) : recs.isError ? (
          <ErrorBox error={recs.error} />
        ) : !recs.data.length ? (
          <Empty />
        ) : (
          <div className="table-wrap" tabIndex={0}>
            <table>
              <thead>
                <tr>
                  <th>Recommendation</th>
                  <th>Created</th>
                  <th>Selected indexes</th>
                  <th>Estimated size</th>
                  <th>Estimated read gain</th>
                  <th>
                    <span className="sr-only">Open</span>
                  </th>
                </tr>
              </thead>
              <tbody>
                {recs.data.slice(0, 5).map((r) => (
                  <tr key={r.id}>
                    <td>
                      <Link className="mono" to={`/recommendations?id=${r.id}`}>
                        {short(r.id)}
                      </Link>
                    </td>
                    <td>{date(r.created_at)}</td>
                    <td>{r.selected_count}</td>
                    <td>{bytes(r.estimated_size_bytes)}</td>
                    <td>
                      {r.estimated_read_improvement_pct == null
                        ? "Unknown"
                        : `${fmt(r.estimated_read_improvement_pct)}%`}
                    </td>
                    <td>
                      <Link
                        to={`/recommendations?id=${r.id}`}
                        aria-label={`Open recommendation ${short(r.id)}`}
                      >
                        <ArrowUpRight size={16} />
                      </Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Panel>
    </>
  );
}
export function Connections() {
  const qc = useQueryClient();
  const nav = useNavigate();
  const connection = useQuery({
    queryKey: ["connection"],
    queryFn: api.connection,
  });
  const validate = useMutation({
    mutationFn: api.validate,
    onSuccess: (data) => qc.setQueryData(["connection"], data),
  });
  const collect = useMutation({
    mutationFn: api.collected,
    onSuccess: (data) => {
      void qc.invalidateQueries();
      nav(`/queries?workload=${data.id}`);
    },
  });
  const d = connection.data;
  return (
    <>
      <PageTitle
        title="Connections"
        description="Inspect the configured local target and the privileges available to analysis."
        action={
          <button
            className="primary"
            disabled={validate.isPending}
            onClick={() => validate.mutate()}
          >
            <Database size={16} />
            {validate.isPending ? "Validating…" : "Validate connection"}
          </button>
        }
      />
      <ErrorBox error={validate.error ?? collect.error} />
      {connection.isPending ? (
        <Busy />
      ) : connection.isError ? (
        <ErrorBox
          error={connection.error}
          retry={() => void connection.refetch()}
        />
      ) : (
        d && (
          <>
            <Panel title="Monitored target">
              <div className="connection-heading">
                <Database size={30} />
                <div>
                  <h3>{d.database}</h3>
                  <p className="muted">
                    {d.role} · {d.server_version}
                  </p>
                </div>
                <Tag tone={d.can_connect ? "success" : "warning"}>
                  {d.can_connect ? "CONNECTED" : "UNAVAILABLE"}
                </Tag>
              </div>
              <dl className="facts">
                <div>
                  <dt>Supported server</dt>
                  <dd>{d.supported_version ? "Yes" : "No"}</dd>
                </div>
                <div>
                  <dt>Read-only analysis</dt>
                  <dd>{d.read_only ? "Enabled" : "Disabled"}</dd>
                </div>
                <div>
                  <dt>Read demo orders</dt>
                  <dd>{d.can_read_orders ? "Allowed" : "Unavailable"}</dd>
                </div>
                <div>
                  <dt>Create target objects</dt>
                  <dd>{d.can_create_schema_objects ? "Allowed" : "Denied"}</dd>
                </div>
                <div>
                  <dt>Superuser</dt>
                  <dd>{d.superuser ? "Yes" : "No"}</dd>
                </div>
                <div>
                  <dt>Temporary objects</dt>
                  <dd>{d.can_create_temp ? "Allowed" : "Denied"}</dd>
                </div>
              </dl>
              <Warnings items={d.warnings} />
            </Panel>
            <div className="two-columns">
              {(["hypopg", "pg_stat_statements"] as const).map((key) => (
                <Panel key={key} title={key}>
                  <Tag tone={d[key].accessible ? "success" : "warning"}>
                    {d[key].accessible ? "ACCESSIBLE" : "UNAVAILABLE"}
                  </Tag>
                  <dl className="facts">
                    <div>
                      <dt>Installed</dt>
                      <dd>{d[key].installed ? "Yes" : "No"}</dd>
                    </div>
                    <div>
                      <dt>Version</dt>
                      <dd>{d[key].version ?? "Unknown"}</dd>
                    </div>
                    <div>
                      <dt>Configured</dt>
                      <dd>
                        {d[key].configured == null
                          ? "Not applicable / unknown"
                          : d[key].configured
                            ? "Yes"
                            : "No"}
                      </dd>
                    </div>
                  </dl>
                  <p className="muted">
                    {key === "hypopg"
                      ? "Session-local hypothetical indexes provide planner estimates without physical deployment."
                      : "Cumulative observations need interval snapshots. They do not provide interval percentiles."}
                  </p>
                </Panel>
              ))}
            </div>
            <Panel title="Collect observed query patterns">
              <p className="muted">
                Create a saved workload from available pg_stat_statements
                entries. Unresolved parameters need representative values before
                planning.
              </p>
              <button
                className="secondary"
                disabled={collect.isPending || !d.pg_stat_statements.accessible}
                onClick={() => collect.mutate()}
              >
                {collect.isPending ? "Collecting…" : "Collect query patterns"}
              </button>
            </Panel>
          </>
        )
      )}
      <p className="muted small">
        Connection credentials stay in the backend’s local secret files. The
        physical benchmark uses the separately guarded indexpilot_bench
        database.
      </p>
    </>
  );
}
