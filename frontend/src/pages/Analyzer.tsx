import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";
import { Plus, Play, Trash2 } from "lucide-react";
import { api, type Model, object } from "../api/client";
import {
  Busy,
  ErrorBox,
  Go,
  PageTitle,
  Panel,
  Warnings,
} from "../components/ui";

const example =
  "SELECT id, user_id, total\nFROM public.orders\nWHERE user_id = 42\nORDER BY created_at DESC\nLIMIT 20;";
type Row = { key: string; sql: string; frequency: string; parameters: string };
export function parseParameters(
  text: string,
): Model<"QueryInput">["parameters"] {
  if (!text.trim()) return {};
  const parsed: unknown = JSON.parse(text);
  if (parsed === null || typeof parsed !== "object" || Array.isArray(parsed))
    throw new Error(
      "Parameters must be a JSON object keyed by parameter number.",
    );
  for (const [key, entry] of Object.entries(parsed)) {
    const p = object(entry);
    if (
      !/^[1-9]\d*$/.test(key) ||
      Number(key) > 100 ||
      ![
        "int8",
        "numeric",
        "text",
        "date",
        "timestamp",
        "timestamptz",
        "bool",
      ].includes(String(p.type)) ||
      !("value" in p) ||
      (p.value !== null &&
        !["string", "number", "boolean"].includes(typeof p.value))
    )
      throw new Error(
        "Each parameter needs a number 1–100, supported type, and scalar value.",
      );
  }
  return parsed as Model<"QueryInput">["parameters"];
}
export function Analyzer() {
  const [mode, setMode] = useState<"queries" | "script" | "file">("queries");
  const [name, setName] = useState("My workload");
  const [rows, setRows] = useState<Row[]>([
    {
      key: crypto.randomUUID(),
      sql: example,
      frequency: "100",
      parameters: "",
    },
  ]);
  const [script, setScript] = useState("");
  const [frequency, setFrequency] = useState("1");
  const [file, setFile] = useState<File | null>(null);
  const [stage, setStage] = useState("");
  const [saved, setSaved] = useState<Model<"WorkloadView"> | null>(null);
  const nav = useNavigate();
  const qc = useQueryClient();
  const run = useMutation({
    mutationFn: async () => {
      setSaved(null);
      const freq = (text: string) => {
        const n = Number(text);
        if (!Number.isFinite(n) || n <= 0 || n > 1e9)
          throw new Error(
            "Frequencies must be greater than zero and at most 1,000,000,000.",
          );
        return n;
      };
      setStage("Saving the workload…");
      let workload: Model<"WorkloadView">;
      if (mode === "queries")
        workload = await api.manual({
          name,
          queries: rows.map((r) => ({
            sql: r.sql,
            frequency: freq(r.frequency),
            parameters: parseParameters(r.parameters),
          })),
        });
      else if (mode === "script")
        workload = await api.sql({
          name,
          sql: script,
          frequency: freq(frequency),
        });
      else {
        if (
          !file ||
          !file.name.toLowerCase().endsWith(".sql") ||
          file.size > 65536
        )
          throw new Error("Choose a UTF-8 .sql file of at most 65,536 bytes.");
        workload = await api.upload(file, name, freq(frequency));
      }
      setSaved(workload);
      if (workload.pattern_total > workload.patterns.length)
        throw new Error(
          "The workload has additional pattern pages. Review it in Query Explorer before choosing an analysis subset.",
        );
      const scenarios = workload.patterns.flatMap((p) => p.scenarios);
      if (
        !scenarios.length ||
        scenarios.some((s) => s.missing_parameters.length)
      )
        throw new Error(
          "Workload saved. Provide representative parameter values in SQL Analyzer before planning every scenario.",
        );
      const ids: string[] = [];
      for (const [index, scenario] of scenarios.entries()) {
        setStage(
          `Capturing PostgreSQL plan ${index + 1} of ${scenarios.length}…`,
        );
        ids.push((await api.planScenario(scenario.id)).id);
      }
      setStage("Generating schema-aware B-Tree candidates…");
      return api.candidates(ids);
    },
    onSuccess: (batch) => {
      void qc.invalidateQueries();
      nav(`/budget?batch=${batch.id}`);
    },
    onSettled: () => {
      void qc.invalidateQueries();
    },
  });
  function update(key: string, values: Partial<Row>) {
    setRows((current) =>
      current.map((r) => (r.key === key ? { ...r, ...values } : r)),
    );
  }
  function submit(e: FormEvent) {
    e.preventDefault();
    run.mutate();
  }
  return (
    <>
      <PageTitle
        title="SQL Analyzer"
        description="Start with representative SELECT queries and their relative frequencies."
      />
      <div className="two-columns analyzer-layout">
        <Panel title="Build a workload">
          <form onSubmit={submit}>
            <fieldset disabled={run.isPending}>
              <div className="segmented" role="group" aria-label="Input format">
                {(["queries", "script", "file"] as const).map((m) => (
                  <button
                    type="button"
                    key={m}
                    className={mode === m ? "active" : ""}
                    aria-pressed={mode === m}
                    onClick={() => setMode(m)}
                  >
                    {m === "queries"
                      ? "Query rows"
                      : m === "script"
                        ? "Paste SQL"
                        : "Upload .sql"}
                  </button>
                ))}
              </div>
              <label>
                Workload name
                <input
                  required
                  maxLength={120}
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                />
              </label>
              {mode === "queries" ? (
                <>
                  {rows.map((r, i) => (
                    <div className="query-input" key={r.key}>
                      <div className="panel-heading">
                        <h3>Query {i + 1}</h3>
                        {rows.length > 1 && (
                          <button
                            type="button"
                            className="icon-button"
                            aria-label={`Remove query ${i + 1}`}
                            onClick={() =>
                              setRows(rows.filter((v) => v.key !== r.key))
                            }
                          >
                            <Trash2 size={16} />
                          </button>
                        )}
                      </div>
                      <label>
                        SQL for query {i + 1}
                        <textarea
                          className="sql-input"
                          required
                          spellCheck={false}
                          value={r.sql}
                          onChange={(e) =>
                            update(r.key, { sql: e.target.value })
                          }
                          rows={7}
                          maxLength={65536}
                        />
                      </label>
                      <label>
                        Relative frequency for query {i + 1}
                        <input
                          type="number"
                          required
                          min="0.000001"
                          max="1000000000"
                          step="any"
                          value={r.frequency}
                          onChange={(e) =>
                            update(r.key, { frequency: e.target.value })
                          }
                        />
                      </label>
                      <details>
                        <summary>Representative parameters (optional)</summary>
                        <label>
                          Parameter JSON for query {i + 1}
                          <textarea
                            className="mono"
                            rows={3}
                            placeholder={'{"1":{"type":"int8","value":42}}'}
                            value={r.parameters}
                            onChange={(e) =>
                              update(r.key, { parameters: e.target.value })
                            }
                          />
                        </label>
                        <p className="muted small">
                          Use parameter numbers without $. Supported types:
                          int8, numeric, text, date, timestamp, timestamptz,
                          bool.
                        </p>
                      </details>
                    </div>
                  ))}
                  <button
                    className="secondary"
                    type="button"
                    disabled={rows.length >= 32}
                    onClick={() =>
                      setRows([
                        ...rows,
                        {
                          key: crypto.randomUUID(),
                          sql: "",
                          frequency: "1",
                          parameters: "",
                        },
                      ])
                    }
                  >
                    <Plus size={16} />
                    Add query
                  </button>
                </>
              ) : (
                <>
                  {mode === "script" ? (
                    <label>
                      SQL statements
                      <textarea
                        required
                        rows={14}
                        className="sql-input"
                        value={script}
                        onChange={(e) => setScript(e.target.value)}
                        maxLength={65536}
                      />
                    </label>
                  ) : (
                    <label>
                      UTF-8 SQL file
                      <input
                        type="file"
                        accept=".sql"
                        required
                        onChange={(e) => setFile(e.target.files?.[0] ?? null)}
                      />
                      <small>Up to 65,536 bytes</small>
                    </label>
                  )}
                  <label>
                    Frequency for each statement
                    <input
                      required
                      type="number"
                      min="0.000001"
                      max="1000000000"
                      step="any"
                      value={frequency}
                      onChange={(e) => setFrequency(e.target.value)}
                    />
                  </label>
                </>
              )}
              <div className="form-footer">
                <button className="primary" type="submit">
                  <Play size={16} />
                  {run.isPending
                    ? "Analyzing…"
                    : "Analyze & generate candidates"}
                </button>
              </div>
            </fieldset>
          </form>
          {run.isPending && <Busy text={stage} />}
          <ErrorBox error={run.error} />
          {saved && (
            <>
              <Go to={`/queries?workload=${saved.id}`}>
                View saved workload {saved.id.slice(0, 8)}
              </Go>
              <Warnings items={saved.warnings} />
            </>
          )}
        </Panel>
        <div>
          <Panel title="Frequency changes the decision">
            <p>
              Frequency weights each query’s root plan cost. A frequently used
              query can justify a different index set than a rare one.
            </p>
            <div className="code-note">
              Workload cost = Σ frequency × root cost
            </div>
            <p className="muted">
              Use relative counts from a representative interval. This is a
              cost-model objective, not a prediction of elapsed time.
            </p>
          </Panel>
          <Panel title="What happens next">
            <ol className="plain-steps">
              <li>Save SQL and explicit frequencies.</li>
              <li>
                Resolve supported syntax against real PostgreSQL catalogs.
              </li>
              <li>Capture EXPLAIN JSON without executing the SELECT.</li>
              <li>Generate bounded candidate indexes.</li>
              <li>Choose a budget and run HypoPG optimization.</li>
            </ol>
            <p className="muted small">
              The initial query is an editable example. No result is shown until
              PostgreSQL returns evidence.
            </p>
          </Panel>
        </div>
      </div>
    </>
  );
}
