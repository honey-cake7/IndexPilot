import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { useId } from "react";
import type { Model } from "../api/client";
import { number } from "../api/client";
import { Empty, fmt } from "./ui";

export function CostChart({
  baseline,
  final,
}: {
  baseline: number | null;
  final: number | null;
}) {
  if (baseline == null || final == null)
    return <Empty title="Planner costs unavailable" />;
  const data = [
    { label: "Baseline", cost: baseline },
    { label: "Selected set", cost: final },
  ];
  return (
    <>
      <div
        className="chart"
        role="figure"
        aria-label="Frequency-weighted root planner costs"
      >
        <ResponsiveContainer width="100%" height={190}>
          <BarChart
            data={data}
            layout="vertical"
            margin={{ left: 15, right: 30 }}
            accessibilityLayer
          >
            <CartesianGrid horizontal={false} stroke="#e6ebef" />
            <XAxis type="number" tickLine={false} axisLine={false} />
            <YAxis
              type="category"
              dataKey="label"
              width={95}
              tickLine={false}
              axisLine={false}
            />
            <Tooltip />
            <Bar
              isAnimationActive={false}
              dataKey="cost"
              fill="#3e6e64"
              radius={[0, 5, 5, 0]}
              maxBarSize={30}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="muted small">
        Planner cost units · weighted root costs · estimates, not milliseconds
      </p>
      <p className="sr-only">
        Baseline {baseline}. Selected set {final}.
      </p>
    </>
  );
}
export function measurementRows(
  measurements: Model<"MeasurementView">[],
  phase: string,
) {
  return ["baseline", "per_query", "indexpilot"].flatMap((arm) => {
    const values = measurements
      .filter((m) => m.arm === arm && m.phase === phase)
      .map((m) => number(m.metrics.mean_ms))
      .filter((n): n is number => n !== null);
    if (!values.length) return [];
    return [
      {
        arm:
          arm === "baseline"
            ? "Baseline"
            : arm === "per_query"
              ? "Per-query"
              : "IndexPilot",
        mean: values.reduce((a, b) => a + b, 0) / values.length,
        repetitions: values.length,
        min: Math.min(...values),
        max: Math.max(...values),
      },
    ];
  });
}
export function MeasuredChart({
  measurements,
  phase = "read_mix",
}: {
  measurements: Model<"MeasurementView">[];
  phase?: string;
}) {
  const id = useId();
  const rows = measurementRows(measurements, phase);
  if (!rows.length)
    return (
      <Empty title="No measured samples for this phase">
        Run the explicit benchmark worker to record real pgbench results.
      </Empty>
    );
  return (
    <>
      <div className="chart" role="figure" aria-labelledby={id}>
        <ResponsiveContainer width="100%" height={230}>
          <BarChart
            data={rows}
            margin={{ left: 10, right: 15, top: 15 }}
            accessibilityLayer
          >
            <CartesianGrid vertical={false} stroke="#e6ebef" />
            <XAxis dataKey="arm" axisLine={false} tickLine={false} />
            <YAxis unit=" ms" axisLine={false} tickLine={false} />
            <Tooltip formatter={(v) => `${fmt(Number(v), 4)} ms`} />
            <Bar
              isAnimationActive={false}
              dataKey="mean"
              name="Mean latency"
              fill="#3e6e64"
              radius={[5, 5, 0, 0]}
              maxBarSize={52}
            />
          </BarChart>
        </ResponsiveContainer>
      </div>
      <p className="small muted" id={id}>
        Measured pgbench transaction latency · {phase} · lower is better
      </p>
      <div className="table-wrap" tabIndex={0}>
        <table>
          <caption className="sr-only">Measured latency summary</caption>
          <thead>
            <tr>
              <th>Arm</th>
              <th>Mean of repetition means</th>
              <th>Repetitions</th>
              <th>Repetition range</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.arm}>
                <td>{r.arm}</td>
                <td>{fmt(r.mean, 4)} ms</td>
                <td>{r.repetitions}</td>
                <td>
                  {fmt(r.min, 4)}–{fmt(r.max, 4)} ms
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
