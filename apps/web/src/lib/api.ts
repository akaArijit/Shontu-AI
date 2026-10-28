import axios, { AxiosInstance, AxiosError } from 'axios';
import { QueryClient } from '@tanstack/react-query';
import { mockApi, useMockApi } from './mockApi';
import type {
  MFDSchemesResponse,
  MFDSchemeSummary,
  FundScoresResponse,
  FundScore,
  AlertsResponse,
  AlertSummary,
  CategoryRankingResponse,
  CategoryRankingResponse as CategoryRankingResponseType,
  PipelineHealth,
  BenchmarkHistory,
  MacroData,
} from '@/types';

const RAW_API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
export const API_BASE = RAW_API_BASE.replace(/\/+$/, '');

if (process.env.NODE_ENV === 'production' && !process.env.NEXT_PUBLIC_API_URL) {
  console.warn(
    '[API] NEXT_PUBLIC_API_URL is not set; falling back to http://localhost:8000. ' +
      'Set it in Vercel and redeploy.'
  );
}

// Real API client
const apiClient = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.response.use(
  (response) => response.data,
  (error: AxiosError) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000,
      gcTime: 10 * 60 * 1000,
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

// Unified API interface - uses mock when in standalone mode, real API otherwise
const createApi = () => {
  const useMock = useMockApi();
  
  if (useMock) {
    console.log('[API] Using MOCK API for standalone development');
    return mockApi;
  }
  
  console.log('[API] Using REAL API');
  return {
    // Scheme Monitoring
    getSchemes: (params: Record<string, unknown> = {}): Promise<MFDSchemesResponse> =>
      apiClient.get('/mfd/schemes', { params }),
    getScheme: (schemeCode: string, asOfDate: string): Promise<MFDSchemeSummary> =>
      apiClient.get(`/mfd/schemes/${schemeCode}`, { params: { as_of_date: asOfDate } }),
    // Scores
    getScores: (params: Record<string, unknown> = {}): Promise<FundScoresResponse> =>
      apiClient.get('/mfd/scores', { params }),
    getScore: (schemeCode: string, asOfDate: string): Promise<FundScore> =>
      apiClient.get(`/mfd/scores/${schemeCode}`, { params: { as_of_date: asOfDate } }),
    getLatestScores: (params: Record<string, unknown> = {}): Promise<FundScoresResponse> =>
      apiClient.get('/mfd/scores/latest', { params }),
    // Alerts
    getAlerts: (params: Record<string, unknown> = {}): Promise<AlertsResponse> =>
      apiClient.get('/mfd/alerts', { params }),
    getAlertsSummary: (asOfDate: string): Promise<AlertSummary[]> =>
      apiClient.get('/mfd/alerts/summary', { params: { as_of_date: asOfDate } }),
    resolveAlert: (alertId: string, resolvedBy: string): Promise<{ success: boolean; alert_id: string }> =>
      apiClient.post(`/mfd/alerts/${alertId}/resolve`, null, { params: { resolved_by: resolvedBy } }),
    dismissAlert: (alertId: string, dismissedBy: string, reason: string): Promise<{ success: boolean; alert_id: string }> =>
      apiClient.post(`/mfd/alerts/${alertId}/dismiss`, null, { params: { dismissed_by: dismissedBy, reason } }),
    bulkResolveAlerts: (alertIds: string[], resolvedBy: string): Promise<{ success: boolean; resolved_count: number }> =>
      apiClient.post('/mfd/alerts/bulk-resolve', { alert_ids: alertIds, resolved_by: resolvedBy }),
    bulkDismissAlerts: (alertIds: string[], dismissedBy: string, reason: string): Promise<{ success: boolean; dismissed_count: number }> =>
      apiClient.post('/mfd/alerts/bulk-dismiss', { alert_ids: alertIds, dismissed_by: dismissedBy, reason }),
    // Rankings
    getCategoryRankings: (category: string, asOfDate: string, metric = 'score', limit = 50): Promise<CategoryRankingResponse> =>
      apiClient.get(`/mfd/rankings/category/${category}`, { params: { as_of_date: asOfDate, metric, limit } }),
    getAllCategoryRankings: (asOfDate: string, limitPerCategory = 20): Promise<CategoryRankingResponseType[]> =>
      apiClient.get('/mfd/rankings/all', { params: { as_of_date: asOfDate, limit_per_category: limitPerCategory } }),
    // Benchmarks & Macro
    getBenchmarkHistory: (benchmarkCode: string, fromDate?: string, toDate?: string): Promise<BenchmarkHistory> =>
      apiClient.get(`/mfd/benchmarks/${benchmarkCode}/history`, { params: { from_date: fromDate, to_date: toDate } }),
    getMacroData: (indicators = 'repo_rate,cpi,usd_inr,india_vix', fromDate?: string, toDate?: string): Promise<MacroData> =>
      apiClient.get('/mfd/macro', { params: { indicators, from_date: fromDate, to_date: toDate } }),
    // Health & Meta
    getHealth: (): Promise<PipelineHealth> => apiClient.get('/mfd/health'),
    getScoringConfig: (version?: string): Promise<{ version: string; effective_date: string; components: Record<string, { weight: number; max_points: number }>; penalty_per_month: number; penalty_cap: number }> =>
      apiClient.get('/mfd/meta/scoring-config', { params: { version } }),
    getRulesConfig: (): Promise<{ alert_rules: Array<{ id: string; condition: string; severity: string; enabled: boolean; category_overrides: Record<string, number> }> }> =>
      apiClient.get('/mfd/meta/rules-config'),
    // CSV Upload
    uploadSchemeMasterCSV: (file: File, dryRun = false): Promise<{ success: boolean; message: string; total_rows: number; valid_rows: number; invalid_rows: number; errors: Array<{ row: number; error: string; data: Record<string, unknown> }>; preview: Array<Record<string, unknown>> }> => {
      const formData = new FormData();
      formData.append('file', file);
      if (dryRun) formData.append('dry_run', 'true');
      return apiClient.post('/mfd/csv/upload/scheme-master', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    },
    downloadSchemeMaster: (): Promise<Blob> =>
      apiClient.get('/mfd/csv/download/scheme-master', { responseType: 'blob' }),
    uploadBenchmarkMappings: (file: File, dryRun = false): Promise<{ success: boolean; message: string; total_rows: number; valid_rows: number; invalid_rows: number; errors: Array<{ row: number; error: string; data: Record<string, unknown> }>; preview: Array<Record<string, unknown>> }> => {
      const formData = new FormData();
      formData.append('file', file);
      if (dryRun) formData.append('dry_run', 'true');
      return apiClient.post('/mfd/csv/upload/benchmark-mappings', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
    },
    downloadBenchmarkTemplate: (): Promise<Blob> =>
      apiClient.get('/mfd/csv/template', { responseType: 'blob' }),
  };
};

export const api = createApi();