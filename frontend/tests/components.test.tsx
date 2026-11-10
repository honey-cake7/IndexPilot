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
import { History } from "../src/pages/History";
import { ReportDetail, Reports } from "../src/pages/Reports";

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

// Report/history fixtures exercise presentation and requests, not database speed.
const reportFixture = {
  id: "report-1",
  title: "Saved report",
  format_version: "indexpilot-report-v1",
  created_at: "2026-11-10T00:00:00Z",
  recommendation_id: "rec-1",
  optimization_id: "opt-1",
  batch_id: "batch-1",
  policy: {
    parameter_policy: "Bound values omitted",
    original_sql_included: true,
    representative_sql_included: false,
  },
  summary: {
    storage_budget_bytes: 0,
    estimated_size_bytes: 0,
    estimated_read_improvement_pct: null,
    final_score: { read_cost: 10 },
  },
  settings: { storage_budget_bytes: 0 },
  provenance: {},
  indexes: [],
  candidates: [],
  search_trials: [],
  benchmarks: [],
  missing_evidence: ["No selected benchmark."],
  warnings: [],
  queries: [
    {
      source_plan_id: "plan-1",
      frequency: 1,
      original_sql: "<img src=x onerror=alert(1)>",
      representative_sql: null,
      explanation: { baseline_cost: 10, final_cost: 10 },
      statistics: [],
    },
  ],
} as unknown as Model<"ReportDocument">;

describe("saved reports and filtered history", () => {
  it("submits explicit report privacy choices and displays the saved report identity", async () => {
    vi.spyOn(api, "recommendations").mockResolvedValue([]);
    vi.spyOn(api, "benchmarks").mockResolvedValue([]);
    vi.spyOn(api, "reports").mockResolvedValue({
      items: [],
      total: 0,
      offset: 0,
      limit: 20,
    });
    const create = vi
      .spyOn(api, "createReport")
      .mockResolvedValue(reportFixture);
    vi.spyOn(api, "report").mockResolvedValue(reportFixture);
    mount(<Reports />, "/reports?id=rec-1");
    expect(screen.getByLabelText(/Include original SQL/)).toBeChecked();
    expect(
      screen.getByLabelText(/Include representative SQL/),
    ).not.toBeChecked();
    await userEvent.clear(screen.getByLabelText("Report title"));
    await userEvent.type(
      screen.getByLabelText("Report title"),
      "A saved decision",
    );
    await userEvent.click(
      screen.getByRole("button", { name: "Save versioned report" }),
    );
    expect(await screen.findByText("report-1", { exact: true })).toBeVisible();
    expect(create).toHaveBeenCalledWith({
      recommendation_id: "rec-1",
      title: "A saved decision",
      benchmark_ids: [],
      include_original_sql: true,
      include_representative_sql: false,
    });
    expect(
      screen.getByRole("link", { name: "Download report Markdown" }),
    ).toHaveAttribute("href", "/api/v1/reports/report-1/download.md");
  });
  it("escapes SQL and report titles in the browser and identifies missing evidence", async () => {
    const rendered = mount(
      <ReportDetail
        report={{ ...reportFixture, title: "<script>evil()</script>" }}
      />,
    );
    expect(
      screen.getByRole("heading", { name: "<script>evil()</script>" }),
    ).toBeVisible();
    await userEvent.click(screen.getByText(/Query 1 .*frequency/));
    expect(screen.getByText("<img src=x onerror=alert(1)>")).toBeVisible();
    expect(rendered.container.querySelector("script,img")).toBeNull();
    expect(screen.getByText("No selected benchmark.")).toBeVisible();
  });
  it("sends history filters to the backend and resets pagination", async () => {
    const history = vi
      .spyOn(api, "history")
      .mockResolvedValue({ items: [], total: 0, offset: 0, limit: 20 });
    mount(<History />, "/history?offset=20");
    await userEvent.selectOptions(
      screen.getByLabelText("Record type"),
      "reports",
    );
    await userEvent.type(screen.getByLabelText("Search title or UUID"), "a_%");
    await userEvent.click(
      screen.getByRole("button", { name: "Apply history filters" }),
    );
    await waitFor(() =>
      expect(history).toHaveBeenLastCalledWith(
        expect.objectContaining({ kind: "reports", q: "a_%", offset: 0 }),
      ),
    );
    expect(screen.getByRole("button", { name: "Next" })).toBeDisabled();
  });
  it("explains reversed date ranges before requesting a new page", async () => {
    const history = vi
      .spyOn(api, "history")
      .mockResolvedValue({ items: [], total: 0, offset: 0, limit: 20 });
    mount(<History />);
    const calls = history.mock.calls.length;
    fireEvent.change(screen.getByLabelText("Saved from (local time)"), {
      target: { value: "2026-11-10T12:00" },
    });
    fireEvent.change(screen.getByLabelText("Saved to (local time)"), {
      target: { value: "2026-11-09T12:00" },
    });
    await userEvent.click(
      screen.getByRole("button", { name: "Apply history filters" }),
    );
    expect(screen.getByRole("alert")).toHaveTextContent(
      "Saved-from must be earlier",
    );
    expect(history.mock.calls.length).toBe(calls);
  });
  it("keeps invalid URL dates recoverable through the error and clear-filter controls", async () => {
    vi.spyOn(api, "history").mockRejectedValue(
      new ApiError("Invalid date range.", "invalid_request"),
    );
    mount(<History />, "/history?from=invalid-date");
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Invalid date range",
    );
    expect(screen.getByRole("button", { name: "Clear filters" })).toBeVisible();
  });
});
