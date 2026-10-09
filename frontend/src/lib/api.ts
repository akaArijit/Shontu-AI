import axios, { AxiosInstance, AxiosError } from 'axios';
import { QueryClient } from '@tanstack/react-query';

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export const apiClient: AxiosInstance = axios.create({
  baseURL: `${API_BASE}/api/v1`,
  timeout: 30000,
  headers: {
    'Content-Type': 'application/json',
  },
});

apiClient.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      gcTime: 10 * 60 * 1000, // 10 minutes
      retry: 1,
      refetchOnWindowFocus: false,
    },
  },
});

export const api = {
  // Scheme Monitoring
  getSchemes: (params: Record<string, unknown> = {}) =>
    apiClient.get('/mfd/schemes', { params }),

  getScheme: (schemeCode: string, asOfDate: string) =>
    apiClient.get(`/mfd/schemes/${schemeCode}`, { params: { as_of_date: asOfDate } }),

  // Scores
  getScores: (params: Record<string, unknown> = {}) =>
    apiClient.get('/mfd/scores', { params }),

  getScore: (schemeCode: string, asOfDate: string) =>
    apiClient.get(`/mfd/scores/${schemeCode}`, { params: { as_of_date: asOfDate } }),

  getLatestScores: (params: Record<string, unknown> = {}) =>
    apiClient.get('/mfd/scores/latest', { params }),

  // Alerts
  getAlerts: (params: Record<string, unknown> = {}) =>
    apiClient.get('/mfd/alerts', { params }),

  getAlertsSummary: (asOfDate: string) =>
    apiClient.get('/mfd/alerts/summary', { params: { as_of_date: asOfDate } }),

  resolveAlert: (alertId: string, resolvedBy: string) =>
    apiClient.post(`/mfd/alerts/${alertId}/resolve`, null, { params: { resolved_by: resolvedBy } }),

  dismissAlert: (alertId: string, dismissedBy: string, reason: string) =>
    apiClient.post(`/mfd/alerts/${alertId}/dismiss`, null, { params: { dismissed_by: dismissedBy, reason } }),

  bulkResolveAlerts: (alertIds: string[], resolvedBy: string) =>
    apiClient.post('/mfd/alerts/bulk-resolve', { alert_ids: alertIds, resolved_by: resolvedBy }),

  bulkDismissAlerts: (alertIds: string[], dismissedBy: string, reason: string) =>
    apiClient.post('/mfd/alerts/bulk-dismiss', { alert_ids: alertIds, dismissed_by: dismissedBy, reason }),

  // Rankings
  getCategoryRankings: (category: string, asOfDate: string, metric = 'score', limit = 50) =>
    apiClient.get(`/mfd/rankings/category/${category}`, { params: { as_of_date: asOfDate, metric, limit } }),

  getAllCategoryRankings: (asOfDate: string, limitPerCategory = 20) =>
    apiClient.get('/mfd/rankings/all', { params: { as_of_date: asOfDate, limit_per_category: limitPerCategory } }),

  // Benchmarks & Macro
  getBenchmarkHistory: (benchmarkCode: string, fromDate?: string, toDate?: string) =>
    apiClient.get(`/mfd/benchmarks/${benchmarkCode}/history`, { params: { from_date: fromDate, to_date: toDate } }),

  getMacroData: (indicators = 'repo_rate,cpi,usd_inr,india_vix', fromDate?: string, toDate?: string) =>
    apiClient.get('/mfd/macro', { params: { indicators, from_date: fromDate, to_date: toDate } }),

  // Health & Meta
  getHealth: () => apiClient.get('/mfd/health'),
  getScoringConfig: (version?: string) => apiClient.get('/mfd/meta/scoring-config', { params: { version } }),
  getRulesConfig: () => apiClient.get('/mfd/meta/rules-config'),
};