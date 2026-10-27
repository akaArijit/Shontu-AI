import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { api } from '@/lib/api';
import type {
  FundScoresResponse,
  FundScore,
  AlertsResponse,
  Alert,
  AlertSummary,
  MFDSchemesResponse,
  MFDSchemeSummary,
  CategoryRankingResponse,
  PipelineHealth,
  BenchmarkHistory,
  MacroData,
} from '@/types';

const AS_OF_DATE_KEY = 'asOfDate';

// Helper to get current as_of_date (defaults to latest available)
export function useAsOfDate() {
  return useQuery({
    queryKey: ['latestAsOfDate'],
    queryFn: async () => {
      const res = await api.getLatestScores({ limit: 1 });
      return res.as_of_date;
    },
    staleTime: 1000 * 60 * 60, // 1 hour
  });
}

// Scheme Monitoring
export function useSchemes(params: Record<string, unknown> = {}) {
  const { data: asOfDate } = useAsOfDate();
  return useQuery<MFDSchemesResponse>({
    queryKey: ['schemes', params, asOfDate],
    queryFn: () => api.getSchemes({ ...params, as_of_date: asOfDate }),
    enabled: !!asOfDate,
  });
}

export function useScheme(schemeCode: string) {
  const { data: asOfDate } = useAsOfDate();
  return useQuery<MFDSchemeSummary>({
    queryKey: ['scheme', schemeCode, asOfDate],
    queryFn: () => api.getScheme(schemeCode, asOfDate!),
    enabled: !!asOfDate && !!schemeCode,
  });
}

// Scores
export function useScores(params: Record<string, unknown> = {}) {
  const { data: asOfDate } = useAsOfDate();
  return useQuery<FundScoresResponse>({
    queryKey: ['scores', params, asOfDate],
    queryFn: () => api.getScores({ ...params, as_of_date: asOfDate }),
    enabled: !!asOfDate,
  });
}

export function useScore(schemeCode: string) {
  const { data: asOfDate } = useAsOfDate();
  return useQuery<FundScore>({
    queryKey: ['score', schemeCode, asOfDate],
    queryFn: () => api.getScore(schemeCode, asOfDate!),
    enabled: !!asOfDate && !!schemeCode,
  });
}

export function useLatestScores(params: Record<string, unknown> = {}) {
  return useQuery<FundScoresResponse>({
    queryKey: ['latestScores', params],
    queryFn: () => api.getLatestScores(params),
  });
}

// Alerts
export function useAlerts(params: Record<string, unknown> = {}) {
  const { data: asOfDate } = useAsOfDate();
  return useQuery<AlertsResponse>({
    queryKey: ['alerts', params, asOfDate],
    queryFn: async (): Promise<AlertsResponse> => {
      const response = await api.getAlerts({ ...params, as_of_date: asOfDate });
      return response;
    },
    enabled: !!asOfDate,
    refetchInterval: 5 * 60 * 1000, // 5 minutes
  });
}

export function useAlertsSummary() {
  const { data: asOfDate } = useAsOfDate();
  return useQuery<AlertSummary[]>({
    queryKey: ['alertsSummary', asOfDate],
    queryFn: () => api.getAlertsSummary(asOfDate!),
    enabled: !!asOfDate,
    refetchInterval: 5 * 60 * 1000,
  });
}

export function useResolveAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ alertId, resolvedBy }: { alertId: string; resolvedBy: string }) =>
      api.resolveAlert(alertId, resolvedBy),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: ['alertsSummary'] });
      queryClient.invalidateQueries({ queryKey: ['schemes'] });
    },
  });
}

export function useDismissAlert() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ alertId, dismissedBy, reason }: { alertId: string; dismissedBy: string; reason: string }) =>
      api.dismissAlert(alertId, dismissedBy, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: ['alertsSummary'] });
      queryClient.invalidateQueries({ queryKey: ['schemes'] });
    },
  });
}

export function useBulkResolveAlerts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ alertIds, resolvedBy }: { alertIds: string[]; resolvedBy: string }) =>
      api.bulkResolveAlerts(alertIds, resolvedBy),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: ['alertsSummary'] });
      queryClient.invalidateQueries({ queryKey: ['schemes'] });
    },
  });
}

export function useBulkDismissAlerts() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ alertIds, dismissedBy, reason }: { alertIds: string[]; dismissedBy: string; reason: string }) =>
      api.bulkDismissAlerts(alertIds, dismissedBy, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['alerts'] });
      queryClient.invalidateQueries({ queryKey: ['alertsSummary'] });
      queryClient.invalidateQueries({ queryKey: ['schemes'] });
    },
  });
}

// Rankings
export function useCategoryRankings(category: string, metric = 'score') {
  const { data: asOfDate } = useAsOfDate();
  return useQuery<CategoryRankingResponse>({
    queryKey: ['categoryRankings', category, metric, asOfDate],
    queryFn: () => api.getCategoryRankings(category, asOfDate!, metric),
    enabled: !!asOfDate && !!category,
  });
}

export function useAllCategoryRankings() {
  const { data: asOfDate } = useAsOfDate();
  return useQuery<CategoryRankingResponse[]>({
    queryKey: ['allCategoryRankings', asOfDate],
    queryFn: () => api.getAllCategoryRankings(asOfDate!),
    enabled: !!asOfDate,
  });
}

// Health & Meta
export function usePipelineHealth() {
  return useQuery<PipelineHealth>({
    queryKey: ['pipelineHealth'],
    queryFn: () => api.getHealth(),
    refetchInterval: 30 * 1000, // 30 seconds
  });
}

export function useScoringConfig(version?: string) {
  return useQuery({
    queryKey: ['scoringConfig', version],
    queryFn: () => api.getScoringConfig(version),
    staleTime: 1000 * 60 * 60,
  });
}

export function useRulesConfig() {
  return useQuery({
    queryKey: ['rulesConfig'],
    queryFn: () => api.getRulesConfig(),
    staleTime: 1000 * 60 * 60,
  });
}

// Benchmarks & Macro
export function useBenchmarkHistory(benchmarkCode: string, fromDate?: string, toDate?: string) {
  return useQuery<BenchmarkHistory>({
    queryKey: ['benchmarkHistory', benchmarkCode, fromDate, toDate],
    queryFn: () => api.getBenchmarkHistory(benchmarkCode, fromDate, toDate),
    enabled: !!benchmarkCode,
  });
}

export function useMacroData(indicators = 'repo_rate,cpi,usd_inr,india_vix') {
  return useQuery<MacroData>({
    queryKey: ['macroData', indicators],
    queryFn: () => api.getMacroData(indicators),
    staleTime: 1000 * 60 * 30, // 30 minutes
  });
}