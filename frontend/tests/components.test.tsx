// Unit fixtures in this file test UI behavior; they are not PostgreSQL evidence.
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, describe, expect, it, vi } from "vitest";
import type { ReactNode } from "react";
import { api, ApiError, type Model } from "../src/api/client";
import { Analyzer, parseParameters } from "../src/pages/Analyzer";
import { Budget, budgetBytes } from "../src/pages/Budget";
import { BenchmarkForm } from "../src/pages/Benchmarks";
import { RecommendationDetail } from "../src/pages/Recommendations";
import { measurementRows, MeasuredChart } from "../src/components/Charts";
import { ErrorBox, fmt } from "../src/components/ui";

afterEach(() => vi.restoreAllMocks());
function mount(element: ReactNode, path = "/") {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[path]}>{element}</MemoryRouter>
    </QueryClientProvider>,
  );
}
const batch: Model<"CandidateBatchView"> = {
  id: "batch-1",
  created_at: "2026-11-09T00:00:00Z",
  catalog_observed_at: "2026-11-09T00:00:00Z",
  source_plan_ids: ["plan-1"],
  options: { max_columns: 3, max_candidates: 32 },
  proposed: [],
  rejected: [],
  attempts: 0,
  unique_considered: 0,
  search_truncated: false,
  warnings: [],
};
const workload: Model<"WorkloadView"> = {
  id: "workload-1",
  name: "Unit fixture",
  source: "manual",
  created_at: "2026-11-09T00:00:00Z",
  patterns: [
    {
      id: "pattern-1",
      identity: "",
      fingerprint: "",
      normalized_sql: "SELECT id FROM orders",
      server_queryid: null,
      server_userid: null,
      server_dbid: null,
      server_toplevel: null,
      scenarios: [
        {
          id: "scenario-1",
          sql: "SELECT id FROM orders",
          representative_sql: "SELECT id FROM orders",
          parameters: {},
          frequency: 100,
          missing_parameters: [],
          validation: "syntax_only",
        },
      ],
    },
  ],
  pattern_total: 1,
  pattern_offset: 0,
  warnings: [],
};

describe("workload input", () => {
  it("sends SQL and frequency, captures every scenario, then navigates to candidates", async () => {
    const manual = vi.spyOn(api, "manual").mockResolvedValue(workload);
    const plan = vi
      .spyOn(api, "planScenario")
      .mockResolvedValue({ id: "plan-1" } as Model<"PlanRecord">);
    const candidates = vi.spyOn(api, "candidates").mockResolvedValue(batch);
    mount(
      <Routes>
        <Route path="/" element={<Analyzer />} />
        <Route path="/budget" element={<p>Budget destination</p>} />
      </Routes>,
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Analyze & generate candidates" }),
    );
    expect(await screen.findByText("Budget destination")).toBeVisible();
    expect(manual.mock.calls[0][0].queries[0]).toMatchObject({
      frequency: 100,
      parameters: {},
    });
    expect(plan).toHaveBeenCalledWith("scenario-1");
    expect(candidates).toHaveBeenCalledWith(["plan-1"]);
  });
  it("preserves the saved workload and reports missing parameters without planning a subset", async () => {
    vi.spyOn(api, "manual").mockResolvedValue({
      ...workload,
      patterns: [
        {
          ...workload.patterns[0],
          scenarios: [
            { ...workload.patterns[0].scenarios[0], missing_parameters: [1] },
          ],
        },
      ],
    });
    const plan = vi.spyOn(api, "planScenario");
    mount(<Analyzer />);
    await userEvent.click(
      screen.getByRole("button", { name: "Analyze & generate candidates" }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Workload saved",
    );
    expect(plan).not.toHaveBeenCalled();
    expect(
      screen.getByRole("link", { name: /View saved workload/ }),
    ).toHaveAttribute("href", "/queries?workload=workload-1");
  });
  it("shows safe API errors and a loading state", async () => {
    let reject!: (e: Error) => void;
    vi.spyOn(api, "manual").mockImplementation(
      () =>
        new Promise((_, r) => {
          reject = r;
        }),
    );
    mount(<Analyzer />);
    await userEvent.click(
      screen.getByRole("button", { name: "Analyze & generate candidates" }),
    );
    expect(screen.getByRole("status")).toHaveTextContent("Saving the workload");
    reject(
      new ApiError(
        "Unsupported SQL construct.",
        "unsupported_sql",
        "request-123",
      ),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent("request-123");
  });
  it("uploads the selected file with its actual frequency", async () => {
    const upload = vi
      .spyOn(api, "upload")
      .mockRejectedValue(new Error("File rejected by backend."));
    mount(<Analyzer />);
    await userEvent.click(screen.getByRole("button", { name: "Upload .sql" }));
    const file = new File(["SELECT id FROM public.orders;"], "queries.sql", {
      type: "text/plain",
    });
    await userEvent.upload(screen.getByLabelText(/UTF-8 SQL file/), file, {
      applyAccept: false,
    });
    // jsdom's native required-file validation differs from Chromium; browser E2E
    // separately submits the actual form using a real file chooser.
    fireEvent.submit(
      screen
        .getByRole("button", { name: "Analyze & generate candidates" })
        .closest("form")!,
    );
    await waitFor(() =>
      expect(upload).toHaveBeenCalledWith(file, "My workload", 1),
    );
  });
  it.each([
    "[]",
    "null",
    '{"0":{"type":"int8","value":1}}',
    '{"1":{"type":"bad","value":1}}',
    '{"1":{"type":"text","value":{}}}',
  ])("rejects invalid parameter object %s", (input) =>
    expect(() => parseParameters(input)).toThrow(),
  );
  it("keeps explicit typed parameter values", () =>
    expect(parseParameters('{"1":{"type":"int8","value":42}}')).toEqual({
      1: { type: "int8", value: 42 },
    }));
});
describe("budget controls", () => {
  it.each([
    ["0", 0],
    ["1", 1048576],
    ["0.125", 131072],
  ])("converts %s MiB into exact integer bytes", (value, expected) =>
    expect(budgetBytes(value)).toBe(expected),
  );
  it.each(["", "-1", "NaN", "Infinity", "99999999999999999999"])(
    "rejects unsafe budget %s",
    (value) => expect(() => budgetBytes(value)).toThrow(),
  );
  it("submits changed budgets to the optimizer and keeps a saved result distinct from edited settings", async () => {
    vi.spyOn(api, "batches").mockResolvedValue([batch]);
    vi.spyOn(api, "batch").mockResolvedValue(batch);
    const run = (id: string, budget: number) =>
      ({
        id,
        batch_id: batch.id,
        created_at: batch.created_at,
        options: {
          storage_budget_bytes: budget,
          max_selected_indexes: 8,
          max_evaluations: 128,
          write_penalty_cost_per_mib: 0,
          max_query_regression_pct: null,
          write_weights: {},
          frequency_basis: "user_supplied_scenario",
        },
        result: {
          baseline_score: { read_cost: 10 },
          final_score: { read_cost: 10, storage_bytes: 0 },
          selected_candidate_ids: [],
          candidates: [],
          trials: [],
          estimated_read_improvement_pct: 0,
          stop_reason: "no_candidates",
          evaluations: 2,
          warnings: [],
        },
      }) as unknown as Model<"OptimizationRunView">;
    vi.spyOn(api, "optimization").mockImplementation(async (id) =>
      run(id, id === "run-zero" ? 0 : 1048576),
    );
    const optimize = vi
      .spyOn(api, "optimize")
      .mockImplementation(async (body) =>
        run(
          body.storage_budget_bytes === 0 ? "run-zero" : "run-one",
          body.storage_budget_bytes,
        ),
      );
    mount(<Budget />, "/budget?batch=batch-1");
    await userEvent.click(
      await screen.findByRole("button", { name: "Run optimization" }),
    );
    expect(await screen.findByText("run-one")).toBeVisible();
    await userEvent.clear(screen.getByLabelText("Storage budget (MiB)"));
    await userEvent.type(screen.getByLabelText("Storage budget (MiB)"), "0");
    expect(
      screen.getByRole("button", { name: "Save recommendation" }),
    ).toBeDisabled();
    await userEvent.click(
      screen.getByRole("button", { name: "Run optimization" }),
    );
    expect(await screen.findByText("run-zero")).toBeVisible();
    expect(optimize.mock.calls.map((c) => c[0].storage_budget_bytes)).toEqual([
      1048576, 0,
    ]);
  });
});
describe("measured evidence and confirmation", () => {
  it("does not chart absent measurements or turn unknown values into zero", () => {
    mount(<MeasuredChart measurements={[]} />);
    expect(
      screen.getByText("No measured samples for this phase"),
    ).toBeVisible();
    expect(fmt(null)).toBe("Unknown");
  });
  it("aggregates only actual finite means in the selected phase", () => {
    const row = (
      arm: string,
      phase: string,
      mean: unknown,
    ): Model<"MeasurementView"> => ({
      id: "unit-row",
      repetition: 1,
      arm,
      phase,
      metrics: { mean_ms: mean },
      conditions: {},
    });
    expect(
      measurementRows(
        [
          row("baseline", "read_mix", 1),
          row("baseline", "read_mix", 3),
          row("baseline", "update", 100),
          row("indexpilot", "read_mix", null),
        ],
        "read_mix",
      ),
    ).toEqual([{ arm: "Baseline", mean: 2, repetitions: 2, min: 1, max: 3 }]);
  });
  it("requires a deliberate checkbox before it queues a physical benchmark", async () => {
    vi.spyOn(api, "recommendations").mockResolvedValue([]);
    const enqueue = vi
      .spyOn(api, "enqueue")
      .mockResolvedValue({ id: "job-1" } as Model<"BenchmarkView">);
    const queued = vi.fn();
    mount(<BenchmarkForm recommendation="rec-1" onQueued={queued} />);
    const button = screen.getByRole("button", {
      name: "Queue confirmed benchmark",
    });
    expect(button).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox"));
    await userEvent.click(button);
    await waitFor(() =>
      expect(enqueue).toHaveBeenCalledWith(
        expect.objectContaining({
          recommendation_id: "rec-1",
          confirm_disposable_benchmark: true,
        }),
      ),
    );
    expect(queued).toHaveBeenCalled();
    await waitFor(() => expect(screen.getByRole("checkbox")).not.toBeChecked());
  });
  it("renders saved recommendation text as text, with estimate units and an empty selection", () => {
    const rec = {
      id: "rec-1",
      optimization_id: "opt-1",
      provenance: {},
      warnings: [],
      indexes: [],
      queries: [],
      summary: {
        message: "<script>alert(1)</script>",
        baseline_score: { read_cost: null },
        final_score: { read_cost: null },
        estimated_size_bytes: 0,
        storage_budget_bytes: 0,
        estimated_read_improvement_pct: null,
      },
    } as unknown as Model<"RecommendationView">;
    const view = mount(<RecommendationDetail rec={rec} />);
    expect(screen.getByText("<script>alert(1)</script>")).toBeVisible();
    expect(view.container.querySelector("script")).toBeNull();
    expect(screen.getByText("Empty selection")).toBeVisible();
    expect(
      screen.getByText("PLANNER ESTIMATE · NOT EXECUTION TIME"),
    ).toBeVisible();
  });
  it("renders a safe actionable error with a request id", async () => {
    const retry = vi.fn();
    mount(
      <ErrorBox
        error={
          new ApiError("Connection unavailable.", "connection_failed", "r-1")
        }
        retry={retry}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "connection_failed · Request r-1",
    );
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
  });
});
