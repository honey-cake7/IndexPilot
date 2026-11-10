import createClient from "openapi-fetch";
import type { components, paths } from "./schema";

export type Model<K extends keyof components["schemas"]> =
  components["schemas"][K];
const client = createClient<paths>();

export class ApiError extends Error {
  constructor(
    message: string,
    readonly code = "request_failed",
    readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
export function object(value: unknown): Record<string, unknown> {
  return value !== null && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}
export function number(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
async function must<T>(
  result: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await result.catch(() => {
    throw new ApiError(
      "Cannot reach the API. Start FastAPI and check the local Vite proxy.",
      "api_unavailable",
    );
  });
  if (!response.ok || data === undefined) {
    const detail = object(object(error).error);
    throw new ApiError(
      typeof detail.message === "string"
        ? detail.message
        : `Request failed (${response.status}).`,
      typeof detail.code === "string" ? detail.code : undefined,
      typeof detail.request_id === "string"
        ? detail.request_id
        : (response.headers.get("X-Request-ID") ?? undefined),
    );
  }
  return data;
}
export const api = {
  history: (
    query: NonNullable<paths["/api/v1/history"]["get"]["parameters"]["query"]>,
  ) => must(client.GET("/api/v1/history", { params: { query } })),
  reports: (offset = 0, q = "", recommendation_id?: string) =>
    must(
      client.GET("/api/v1/reports", {
        params: { query: { offset, limit: 20, q, recommendation_id } },
      }),
    ),
  report: (id: string) =>
    must(
      client.GET("/api/v1/reports/{report_id}", {
        params: { path: { report_id: id } },
      }),
    ),
  createReport: (body: Model<"ReportRequest">) =>
    must(client.POST("/api/v1/reports", { body })),
  ready: () => must(client.GET("/health/ready")),
  overview: () => must(client.GET("/api/v1/overview")),
  connection: () => must(client.GET("/api/v1/connections/demo")),
  validate: () =>
    must(
      client.POST("/api/v1/connections/validate", { body: { target: "demo" } }),
    ),
  workloads: (offset = 0) =>
    must(
      client.GET("/api/v1/workloads", {
        params: { query: { limit: 20, offset } },
      }),
    ),
  workload: (id: string, offset = 0) =>
    must(
      client.GET("/api/v1/workloads/{workload_id}", {
        params: { path: { workload_id: id }, query: { limit: 100, offset } },
      }),
    ),
  manual: (body: Model<"ManualWorkloadInput">) =>
    must(client.POST("/api/v1/workloads/manual", { body })),
  sql: (body: Model<"SQLWorkloadInput">) =>
    must(client.POST("/api/v1/workloads/sql", { body })),
  collected: () =>
    must(
      client.POST("/api/v1/workloads/collected", {
        body: { name: "Collected from pg_stat_statements" },
      }),
    ),
  upload: async (
    file: File,
    name: string,
    frequency: number,
  ): Promise<Model<"WorkloadView">> => {
    const body = new FormData();
    body.set("file", file);
    body.set("name", name);
    body.set("frequency", String(frequency));
    const response = await fetch("/api/v1/workloads/upload", {
      method: "POST",
      body,
    });
    return must(
      Promise.resolve({
        data: response.ok
          ? ((await response.json()) as Model<"WorkloadView">)
          : undefined,
        error: response.ok ? undefined : await response.json(),
        response,
      }),
    );
  },
  plans: (offset = 0) =>
    must(
      client.GET("/api/v1/plans", { params: { query: { limit: 20, offset } } }),
    ),
  plan: (id: string) =>
    must(
      client.GET("/api/v1/plans/{plan_id}", {
        params: { path: { plan_id: id } },
      }),
    ),
  planScenario: (id: string) =>
    must(
      client.POST("/api/v1/query-scenarios/{scenario_id}/plan", {
        params: { path: { scenario_id: id } },
      }),
    ),
  batches: (offset = 0) =>
    must(
      client.GET("/api/v1/candidates", {
        params: { query: { limit: 20, offset } },
      }),
    ),
  batch: (id: string) =>
    must(
      client.GET("/api/v1/candidates/{batch_id}", {
        params: { path: { batch_id: id } },
      }),
    ),
  candidates: (plan_ids: string[]) =>
    must(
      client.POST("/api/v1/candidates", {
        body: { plan_ids, max_columns: 3, max_candidates: 32 },
      }),
    ),
  optimizations: (offset = 0) =>
    must(
      client.GET("/api/v1/optimizations", {
        params: { query: { limit: 20, offset } },
      }),
    ),
  optimization: (id: string) =>
    must(
      client.GET("/api/v1/optimizations/{optimization_id}", {
        params: { path: { optimization_id: id } },
      }),
    ),
  optimize: (body: Model<"OptimizationRequest">) =>
    must(client.POST("/api/v1/optimizations", { body })),
  recommendations: (offset = 0) =>
    must(
      client.GET("/api/v1/recommendations", {
        params: { query: { limit: 20, offset } },
      }),
    ),
  recommendation: (id: string) =>
    must(
      client.GET("/api/v1/recommendations/{recommendation_id}", {
        params: { path: { recommendation_id: id } },
      }),
    ),
  recommend: (optimization_id: string) =>
    must(client.POST("/api/v1/recommendations", { body: { optimization_id } })),
  deployment: (id: string) =>
    must(
      client.GET("/api/v1/recommendations/{recommendation_id}/deployment-sql", {
        params: { path: { recommendation_id: id } },
      }),
    ),
  benchmarks: (offset = 0, recommendation_id?: string) =>
    must(
      client.GET("/api/v1/benchmarks", {
        params: { query: { limit: 20, offset, recommendation_id } },
      }),
    ),
  benchmark: (id: string) =>
    must(
      client.GET("/api/v1/benchmarks/{job_id}", {
        params: { path: { job_id: id } },
      }),
    ),
  enqueue: (body: Model<"BenchmarkRequest">) =>
    must(client.POST("/api/v1/benchmarks", { body })),
  cancel: (id: string) =>
    must(
      client.POST("/api/v1/benchmarks/{job_id}/cancel", {
        params: { path: { job_id: id } },
      }),
    ),
  measurements: (id: string) =>
    must(
      client.GET("/api/v1/benchmarks/{job_id}/measurements", {
        params: { path: { job_id: id } },
      }),
    ),
};
