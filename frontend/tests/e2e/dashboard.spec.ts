// These tests use the real API, local PostgreSQL and HypoPG. No network mocking.
// Named e2e-* metadata is retained as reviewable evidence. Target public tables
// are read only; the explicitly confirmed benchmark cleans its private schema.
import { test, expect, type APIRequestContext } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { execFileSync } from "node:child_process";
import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";

const stamp = crypto.randomUUID();
const screenshots = resolve(
  process.env.INDEXPILOT_SCREENSHOT_DIR ?? "../artifacts/screenshots",
);
let recommendationId = "";
let optimizationId = "";
let benchmarkId = "";
let reportId = "";
let initialReportId = "";

async function checked(request: APIRequestContext, path: string) {
  const response = await request.get(path);
  expect(response.ok(), await response.text()).toBeTruthy();
  return response.json();
}
test.describe.serial("real PostgreSQL dashboard", () => {
  test("workload → plans → candidates → saved budgets → recommendation → downloads", async ({
    page,
    request,
  }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.goto("/analyzer");
    await page.getByLabel("Workload name").fill(`e2e-${stamp}`);
    await page
      .getByLabel("SQL for query 1")
      .fill("SELECT id,status FROM public.orders WHERE user_id=101");
    await page.getByLabel("Relative frequency for query 1").fill("100");
    await page.getByRole("button", { name: "Add query", exact: true }).click();
    await page
      .getByLabel("SQL for query 2")
      .fill("SELECT id,total FROM public.orders WHERE status='paid'");
    await page.getByLabel("Relative frequency for query 2").fill("25");
    await page
      .getByRole("button", { name: "Analyze & generate candidates" })
      .click();
    await expect(page).toHaveURL(/\/budget\?batch=/);
    const batchId = new URL(page.url()).searchParams.get("batch")!;
    const batch = await checked(request, `/api/v1/candidates/${batchId}`);
    expect(batch.source_plan_ids).toHaveLength(2);
    expect(batch.proposed.length).toBeGreaterThan(0);
    await page
      .getByRole("button", { name: "Run optimization", exact: true })
      .click();
    await expect(page).toHaveURL(/optimization=/);
    optimizationId = new URL(page.url()).searchParams.get("optimization")!;
    const first = await checked(
      request,
      `/api/v1/optimizations/${optimizationId}`,
    );
    expect(first.options.storage_budget_bytes).toBe(1048576);
    expect(first.cleanup_confirmed).toBe(true);
    expect(first.result.selected_candidate_ids.length).toBeGreaterThan(0);
    await page.getByLabel("Storage budget (MiB)", { exact: true }).fill("0");
    await expect(
      page.getByRole("button", { name: "Save recommendation" }),
    ).toBeDisabled();
    await page
      .getByRole("button", { name: "Run optimization", exact: true })
      .click();
    await expect
      .poll(() => new URL(page.url()).searchParams.get("optimization"))
      .not.toBe(optimizationId);
    const zeroId = new URL(page.url()).searchParams.get("optimization")!;
    const zero = await checked(request, `/api/v1/optimizations/${zeroId}`);
    expect(zero.options.storage_budget_bytes).toBe(0);
    expect(zero.result.selected_candidate_ids).toHaveLength(0);
    expect(
      (await checked(request, `/api/v1/optimizations/${optimizationId}`))
        .options.storage_budget_bytes,
    ).toBe(1048576);
    await page.goto(`/budget?optimization=${optimizationId}`);
    await page.getByRole("button", { name: "Save recommendation" }).click();
    await expect(page).toHaveURL(/\/recommendations\?id=/);
    recommendationId = new URL(page.url()).searchParams.get("id")!;
    await expect(
      page.getByText("PLANNER ESTIMATE · NOT EXECUTION TIME"),
    ).toBeVisible();
    await page.getByRole("button", { name: "Show deployment SQL" }).click();
    await expect(
      page.getByRole("button", { name: "Download .sql", exact: true }),
    ).toBeVisible();
    const sqlDownload = page.waitForEvent("download");
    await page
      .getByRole("button", { name: "Download .sql", exact: true })
      .click();
    expect((await sqlDownload).suggestedFilename()).toBe(
      `indexpilot-${recommendationId}.sql`,
    );
    await page
      .getByRole("link", { name: "Download evidence", exact: true })
      .click();
    await page
      .getByLabel("Report title", { exact: true })
      .fill(`e2e-report-${stamp}`);
    await page.getByRole("button", { name: "Save versioned report" }).click();
    await expect(page).toHaveURL(/report=/);
    initialReportId = new URL(page.url()).searchParams.get("report")!;
    const jsonDownload = page.waitForEvent("download");
    await page.getByRole("link", { name: "Download report JSON" }).click();
    expect((await jsonDownload).suggestedFilename()).toBe(
      `indexpilot-report-${initialReportId}.json`,
    );
    expect(errors).toEqual([]);
  });
  test("file upload and typed representative parameters reach PostgreSQL", async ({
    page,
    request,
  }) => {
    await page.goto("/analyzer");
    await page.getByLabel("Workload name").fill(`e2e-upload-${stamp}`);
    await page
      .getByRole("button", { name: "Upload .sql", exact: true })
      .click();
    await page.getByLabel(/UTF-8 SQL file/).setInputFiles({
      name: "workload.sql",
      mimeType: "text/plain",
      buffer: Buffer.from("SELECT id FROM public.orders WHERE user_id=73;"),
    });
    await page.getByLabel("Frequency for each statement").fill("17");
    await page
      .getByRole("button", { name: "Analyze & generate candidates" })
      .click();
    await expect(page).toHaveURL(/\/budget\?batch=/);
    const batch = await checked(
      request,
      `/api/v1/candidates/${new URL(page.url()).searchParams.get("batch")}`,
    );
    const plan = await checked(
      request,
      `/api/v1/plans/${batch.source_plan_ids[0]}`,
    );
    expect(plan.frequency).toBe(17);
    await page.goto(`/queries?plan=${plan.id}`);
    await expect(page.locator(".plan-node").first()).toBeVisible();
    await page.goto("/analyzer");
    await page.getByLabel("Workload name").fill(`e2e-parameters-${stamp}`);
    await page
      .getByLabel("SQL for query 1")
      .fill("SELECT id FROM public.orders WHERE user_id=$1");
    await page
      .getByText("Representative parameters (optional)", { exact: true })
      .click();
    await page
      .getByLabel("Parameter JSON for query 1")
      .fill('{"1":{"type":"int8","value":42}}');
    await page
      .getByRole("button", { name: "Analyze & generate candidates" })
      .click();
    await expect(page).toHaveURL(/\/budget\?batch=/);
  });
  test("explicit confirmation queues and cancels, then a real worker supplies measured charts", async ({
    page,
    request,
  }) => {
    await page.goto(`/benchmarks?recommendation=${recommendationId}`);
    const button = page.getByRole("button", {
      name: "Queue confirmed benchmark",
    });
    await expect(button).toBeDisabled();
    await page.getByRole("checkbox").check();
    await button.click();
    await expect(page).toHaveURL(/job=/);
    const cancelledId = new URL(page.url()).searchParams.get("job")!;
    await page.getByRole("button", { name: "Request cancellation" }).click();
    await expect
      .poll(
        async () =>
          (await checked(request, `/api/v1/benchmarks/${cancelledId}`)).status,
      )
      .toBe("cancelled");
    await page.goto(`/benchmarks?recommendation=${recommendationId}`);
    await page
      .getByText("Dataset & measurement settings", { exact: true })
      .click();
    for (const [label, value] of [
      ["Order rows", "1000"],
      ["Repetitions", "1"],
      ["Transactions per client / phase", "10"],
      ["Read warmup per client", "0"],
    ])
      await page.getByLabel(label, { exact: true }).fill(value);
    await page.getByRole("checkbox").check();
    await page
      .getByRole("button", { name: "Queue confirmed benchmark" })
      .click();
    await expect(page).toHaveURL(/job=/);
    benchmarkId = new URL(page.url()).searchParams.get("job")!;
    // Refuses to run if another queued/running/unclean job exists. It does not
    // consume a user's unrelated queued benchmark for test convenience.
    execFileSync(
      "uv",
      ["run", "python", "frontend/tests/run_e2e_benchmark.py", benchmarkId],
      { cwd: resolve(".."), timeout: 60000, stdio: "pipe" },
    );
    await page.reload();
    await expect(page.getByText("COMPLETED", { exact: true })).toBeVisible();
    await expect(
      page.getByText("Cleanup verified", { exact: true }),
    ).toBeVisible();
    const measures = await checked(
      request,
      `/api/v1/benchmarks/${benchmarkId}/measurements`,
    );
    expect(measures.length).toBe(18);
    await expect(
      page.getByRole("table", { name: "Measured latency summary" }),
    ).toBeVisible();
    const baseline = measures.find(
      (m: { arm: string; phase: string }) =>
        m.arm === "baseline" && m.phase === "read_mix",
    );
    const value = baseline.metrics.mean_ms.toLocaleString(undefined, {
      maximumFractionDigits: 4,
    });
    await expect(
      page
        .getByRole("table", { name: "Measured latency summary" })
        .getByText(`${value} ms`, { exact: true }),
    ).toBeVisible();
    await page.getByLabel("Measured phase").selectOption("update");
    await expect(
      page.getByText(
        "Measured pgbench transaction latency · update · lower is better",
      ),
    ).toBeVisible();
  });
  test("saved measured reports, Markdown and filtered history survive reload", async ({
    page,
    request,
  }) => {
    await page.goto(`/reports?id=${recommendationId}`);
    await page
      .getByLabel("Report title", { exact: true })
      .fill(`e2e-measured-${stamp}`);
    await page
      .getByText("Choose benchmark evidence (0/5 selected)", { exact: true })
      .click();
    await page
      .getByLabel(new RegExp(`Include benchmark ${benchmarkId.slice(0, 8)}`))
      .check();
    await page.getByRole("button", { name: "Save versioned report" }).click();
    await expect(page).toHaveURL(/report=/);
    reportId = new URL(page.url()).searchParams.get("report")!;
    const stored = await checked(request, `/api/v1/reports/${reportId}`);
    expect(stored.benchmarks[0].id).toBe(benchmarkId);
    expect(stored.benchmarks[0].complete_comparison).toBe(true);
    expect(stored.benchmarks[0].measurements.length).toBe(18);
    const downloadPromise = page.waitForEvent("download");
    await page.getByRole("link", { name: "Download report Markdown" }).click();
    const download = await downloadPromise;
    expect(download.suggestedFilename()).toBe(
      `indexpilot-report-${reportId}.md`,
    );
    const md = readFileSync((await download.path())!, "utf8");
    expect(md).toContain("indexpilot-report-v1");
    expect(md).toContain(benchmarkId);
    expect(md).toContain("planner_cost");
    await page.reload();
    await expect(
      page.getByRole("heading", { name: `e2e-measured-${stamp}`, exact: true }),
    ).toBeVisible();
    await page
      .getByLabel("Compare with another report")
      .selectOption(initialReportId);
    await expect(
      page.getByText("These reports refer to the same candidate batch.", {
        exact: false,
      }),
    ).toBeVisible();
    await page.goto("/history");
    await page.getByLabel("Record type").selectOption("reports");
    await page.getByLabel("Search title or UUID").fill(reportId);
    await page.getByRole("button", { name: "Apply history filters" }).click();
    await expect(
      page.getByText("1 matching records", { exact: true }),
    ).toBeVisible();
    await page.getByRole("link", { name: "View", exact: true }).click();
    await expect(page).toHaveURL(new RegExp(`report=${reportId}`));
    await expect(
      page.getByRole("heading", { name: `e2e-measured-${stamp}`, exact: true }),
    ).toBeVisible();
    mkdirSync(screenshots, { recursive: true });
    await page.screenshot({
      path: join(screenshots, "reports.png"),
      fullPage: true,
    });
  });
  test("saved report survives real API process restart", async ({ page }) => {
    expect(reportId).not.toBe("");
    const proof = JSON.parse(
      execFileSync(
        "uv",
        ["run", "python", "scripts/verify_restart.py", reportId],
        { cwd: resolve(".."), timeout: 45000, encoding: "utf8" },
      ),
    );
    expect(proof).toMatchObject({
      report_id: reportId,
      api_process_starts: 2,
      content_unchanged: true,
    });
    await page.goto(`/reports?report=${reportId}`);
    await expect(
      page.getByRole("heading", { name: `e2e-measured-${stamp}`, exact: true }),
    ).toBeVisible();
    writeFileSync(
      test.info().outputPath("restart-proof.json"),
      JSON.stringify(proof, null, 2),
    );
  });
  test("all nine views pass desktop/mobile accessibility and overflow checks", async ({
    page,
    request,
  }) => {
    // Allows this read-only audit to be rerun by title after the real flow.
    if (!recommendationId) {
      const recs = await checked(request, "/api/v1/recommendations?limit=1");
      expect(recs.length).toBeGreaterThan(0);
      recommendationId = recs[0].id;
      optimizationId = recs[0].optimization_id;
      const savedReports = await checked(
        request,
        `/api/v1/reports?recommendation_id=${recommendationId}&limit=1`,
      );
      reportId = savedReports.items[0]?.id ?? "";
      const jobs = await checked(request, "/api/v1/benchmarks?limit=100");
      benchmarkId =
        jobs.find(
          (j: { status: string; cleanup_confirmed: boolean }) =>
            j.status === "completed" && j.cleanup_confirmed,
        )?.id ?? "";
    }
    const routes = [
      "/",
      "/connections",
      "/analyzer",
      "/queries",
      `/recommendations?id=${recommendationId}`,
      `/budget?optimization=${optimizationId}`,
      `/benchmarks?job=${benchmarkId}`,
      "/history",
      `/reports?id=${recommendationId}${reportId ? `&report=${reportId}` : ""}`,
    ];
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      for (const route of routes) {
        await page.goto(route);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        await expect(page.getByRole("status")).toHaveCount(0);
        await expect(page.getByRole("alert")).toHaveCount(0);
        const results = await new AxeBuilder({ page })
          .withTags(["wcag2a", "wcag2aa", "wcag21aa"])
          .analyze();
        if (results.violations.length)
          writeFileSync(
            test.info().outputPath("accessibility.json"),
            JSON.stringify(results.violations, null, 2),
          );
        expect(
          results.violations,
          `${width}px ${route}: ${JSON.stringify(results.violations.map((v) => ({ id: v.id, nodes: v.nodes.map((n) => n.target) })))}`,
        ).toEqual([]);
        const overflow = await page.evaluate(() => ({
          width: innerWidth,
          scroll: document.documentElement.scrollWidth,
          elements: Array.from(document.querySelectorAll("body *"))
            .filter((e) => e.getBoundingClientRect().right > innerWidth + 1)
            .map((e) => ({
              tag: e.tagName,
              cls: e.className?.toString(),
              right: e.getBoundingClientRect().right,
              overflow: getComputedStyle(e).overflowX,
              parentOverflow:
                e.parentElement && getComputedStyle(e.parentElement).overflowX,
            }))
            .slice(0, 20),
        }));
        expect(
          overflow.scroll <= overflow.width + 1,
          `${width}px ${route} horizontal overflow ${JSON.stringify(overflow)}`,
        ).toBeTruthy();
      }
    }
    await page.goto("/");
    await page.keyboard.press("Tab");
    await expect(
      page.getByRole("link", { name: "Skip to content" }),
    ).toBeFocused();
    await page.keyboard.press("Enter");
    await expect(page.locator("#main")).toBeFocused();
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.keyboard.press("Escape");
    await expect(
      page.getByRole("button", { name: "Open navigation" }),
    ).toBeFocused();
    await page.getByRole("button", { name: "Open navigation" }).click();
    await page.getByRole("link", { name: "SQL Analyzer", exact: true }).click();
    await expect(page).toHaveURL("/analyzer");
    mkdirSync(screenshots, { recursive: true });
    await page.screenshot({
      path: join(screenshots, "analyzer-mobile.png"),
      fullPage: true,
    });
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto("/");
    await expect(
      page.getByRole("heading", { name: "Recent recommendations" }),
    ).toBeVisible();
    await expect(page.getByRole("status")).toHaveCount(0);
    await expect(page.locator(".recharts-bar-rectangle").first()).toBeVisible();
    await page.screenshot({
      path: join(screenshots, "dashboard.png"),
      fullPage: true,
    });
    if (reportId) {
      await page.goto(`/reports?report=${reportId}`);
      await expect(
        page.getByRole("heading", {
          name: "Selected index explanations",
          exact: true,
        }),
      ).toBeVisible();
      await page.screenshot({
        path: join(screenshots, "reports.png"),
        fullPage: true,
      });
    }
  });
});
