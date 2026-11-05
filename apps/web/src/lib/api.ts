import type {
  BenchmarkGraphResponse,
  BenchmarkLevelImportResponse,
  BenchmarkLevelsResponse,
  BenchmarkMappingChangeResponse,
  BenchmarkMappingResponse,
  BenchmarkMappingUpdateResponse,
  BusinessReviewResponse,
  ConfirmResponse,
  DashboardResponse,
  KeywordMappingPreview,
  MappingFilePreview,
  PreviewResponse,
} from "@/lib/types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") ||
  "http://127.0.0.1:8000";

async function parseResponse<T>(response: Response): Promise<T> {
  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = text;
    }
  }
  if (!response.ok) {
    let detail = `Request failed with status ${response.status}`;
    if (payload && typeof payload === "object" && "detail" in payload) {
      const raw = (payload as { detail: unknown }).detail;
      if (typeof raw === "string") {
        detail = raw;
      } else if (Array.isArray(raw)) {
        detail = raw
          .map((item) => {
            if (!item || typeof item !== "object") return String(item);
            const row = item as { msg?: unknown; loc?: unknown };
            const location = Array.isArray(row.loc)
              ? row.loc.join(".")
              : "";
            const message =
              typeof row.msg === "string" ? row.msg : "Invalid request";
            return location ? `${location}: ${message}` : message;
          })
          .join(" ");
      } else if (raw) {
        detail = String(raw);
      }
    }
    throw new Error(detail);
  }
  return payload as T;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`, {
    cache: "no-store",
    ...init,
  });
  return parseResponse<T>(response);
}

export const api = {
  baseUrl: API_BASE,
  dashboard: () => request<DashboardResponse>("/api/v1/dashboard"),
  businessReview: (filters?: {
    performance?: string;
    benchmark?: string;
    client?: string;
    minCurrentValue?: number | null;
    sort?: string;
    direction?: string;
  }) => {
    const params = new URLSearchParams();
    if (filters?.performance && filters.performance !== "all") {
      params.set("performance", filters.performance);
    }
    if (filters?.benchmark && filters.benchmark !== "all") {
      params.set("benchmark", filters.benchmark);
    }
    if (filters?.client && filters.client !== "all") {
      params.set("client", filters.client);
    }
    if (
      filters?.minCurrentValue !== null &&
      filters?.minCurrentValue !== undefined &&
      Number.isFinite(filters.minCurrentValue)
    ) {
      params.set("min_current_value", String(filters.minCurrentValue));
    }
    if (filters?.sort && filters.sort !== "current_value") {
      params.set("sort", filters.sort);
    }
    if (filters?.direction && filters.direction !== "desc") {
      params.set("direction", filters.direction);
    }
    const query = params.toString();
    return request<BusinessReviewResponse>(
      `/api/v1/business-review${query ? `?${query}` : ""}`,
    );
  },
  benchmarkGraph: () =>
    request<BenchmarkGraphResponse>("/api/v1/benchmark-graph"),
  previewImport: (formData: FormData) =>
    request<PreviewResponse>("/api/v1/imports/preview", {
      method: "POST",
      body: formData,
    }),
  confirmImport: (importId: string) =>
    request<ConfirmResponse>(`/api/v1/imports/${importId}/confirm`, {
      method: "POST",
    }),
  loadDemo: (replace: boolean) =>
    request<ConfirmResponse>(`/api/v1/demo/load?replace=${replace}`, {
      method: "POST",
    }),
  benchmarkMappings: () =>
    request<BenchmarkMappingResponse>("/api/v1/benchmark-mappings"),
  updateBenchmarkMapping: (schemeId: number, benchmarkName: string) =>
    request<BenchmarkMappingUpdateResponse>(
      `/api/v1/benchmark-mappings/${schemeId}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ benchmark_name: benchmarkName }),
      },
    ),
  bulkUpdateBenchmarkMappings: (
    schemeIds: number[],
    benchmarkName: string,
  ) =>
    request<BenchmarkMappingChangeResponse>("/api/v1/benchmark-mappings/bulk", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        scheme_ids: schemeIds,
        benchmark_name: benchmarkName,
      }),
    }),
  acceptBenchmarkSuggestions: (schemeIds?: number[]) =>
    request<BenchmarkMappingChangeResponse>(
      "/api/v1/benchmark-mappings/accept-suggestions",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(
          schemeIds === undefined ? {} : { scheme_ids: schemeIds },
        ),
      },
    ),
  acceptHighConfidenceSuggestions: () =>
    request<BenchmarkMappingChangeResponse>(
      "/api/v1/benchmark-mappings/accept-high-confidence",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
      },
    ),
  keywordBenchmarkMapping: (
    keyword: string,
    benchmarkName: string,
    apply: boolean,
  ) =>
    request<KeywordMappingPreview>("/api/v1/benchmark-mappings/keyword", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        keyword,
        benchmark_name: benchmarkName,
        apply,
      }),
    }),
  benchmarkMappingExportUrl: (format: "csv" | "xlsx") =>
    `${API_BASE}/api/v1/benchmark-mappings/export?format=${format}`,
  previewBenchmarkMappingImport: (formData: FormData) =>
    request<MappingFilePreview>("/api/v1/benchmark-mappings/import/preview", {
      method: "POST",
      body: formData,
    }),
  applyBenchmarkMappingImport: (formData: FormData) =>
    request<MappingFilePreview>("/api/v1/benchmark-mappings/import/apply", {
      method: "POST",
      body: formData,
    }),
  resetData: () =>
    request<{ status: string; message: string }>("/api/v1/data/reset", {
      method: "POST",
    }),
  benchmarkLevels: () =>
    request<BenchmarkLevelsResponse>("/api/v1/benchmarks/levels"),
  importBenchmarkLevels: (formData: FormData) =>
    request<BenchmarkLevelImportResponse>("/api/v1/benchmarks/levels/import", {
      method: "POST",
      body: formData,
    }),
  refreshBenchmarkLevels: (years: number) =>
    request<{ succeeded: number; failed: number; attempted: number; date_range: { from: string; to: string }; errors: { benchmark: string; error: string }[] }>(
      "/api/v1/benchmarks/levels/refresh",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ years }),
      },
    ),
};
