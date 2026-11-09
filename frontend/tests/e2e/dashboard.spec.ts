// These tests use the real API, local PostgreSQL and HypoPG. No network mocking.
// Named e2e-* metadata is retained as reviewable evidence. Target public tables
// are read only; the explicitly confirmed benchmark cleans its private schema.
import { test, expect, type APIRequestContext } from "@playwright/test";
import AxeBuilder from "@axe-core/playwright";
import { execFileSync } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { resolve } from "node:path";

const stamp = crypto.randomUUID();
let recommendationId = "";
let optimizationId = "";
let benchmarkId = "";

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
    const jsonDownload = page.waitForEvent("download");
    await page.getByRole("button", { name: "Download analysis JSON" }).click();
    expect((await jsonDownload).suggestedFilename()).toBe(
      `indexpilot-analysis-${recommendationId}.json`,
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
      `/reports?id=${recommendationId}`,
    ];
    for (const width of [1440, 390]) {
      await page.setViewportSize({ width, height: 1000 });
      for (const route of routes) {
        await page.goto(route);
        await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
        await expect(page.getByRole("status")).toHaveCount(0);
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
    mkdirSync(resolve("../docs/screenshots"), { recursive: true });
    await page.screenshot({
      path: "../docs/screenshots/analyzer-mobile.png",
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
      path: "../docs/screenshots/dashboard.png",
      fullPage: true,
    });
  });
});
