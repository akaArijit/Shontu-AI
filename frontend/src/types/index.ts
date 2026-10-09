export interface ScoreBreakdownItem {
  component: string;
  points: number;
  max_points: number;
  reason: string;
  raw_value?: number;
}

export interface FundScore {
  scheme_code: string;
  scheme_name: string;
  category: string;
  amc: string;
  benchmark_name: string;
  fund_health_score: number;
  category_rank?: number;
  category_percentile?: number;
  penalty: number;
  breakdown: ScoreBreakdownItem[];
  scoring_config_version: string;
  as_of_date: string;
}

export interface FundScoresResponse {
  as_of_date: string;
  total: number;
  limit: number;
  offset: number;
  scores: FundScore[];
}

export interface Alert {
  alert_id: string;
  scheme_code: string;
  scheme_name: string;
  category: string;
  alert_type: string;
  severity: 'low' | 'medium' | 'high';
  triggered_on: string;
  resolved_on?: string;
  details: Record<string, unknown>;
}

export interface AlertsResponse {
  as_of_date: string;
  total: number;
  limit: number;
  offset: number;
  alerts: Alert[];
}

export interface AlertSummary {
  alert_type: string;
  severity: string;
  count: number;
  schemes_affected: number;
  latest_triggered: string;
}

export interface MFDSchemeSummary {
  scheme_code: string;
  scheme_name: string;
  amc: string;
  category: string;
  benchmark_name: string;
  fund_health_score: number;
  category_rank?: number;
  category_percentile?: number;
  return_1y?: number;
  alpha_1y?: number;
  max_drawdown_1y?: number;
  volatility_1y?: number;
  consecutive_underperf_months: number;
  high_alerts: number;
  medium_alerts: number;
  low_alerts: number;
}

export interface MFDSchemesResponse {
  as_of_date: string;
  total: number;
  limit: number;
  offset: number;
  schemes: MFDSchemeSummary[];
}

export interface CategoryRankingItem {
  category: string;
  scheme_code: string;
  scheme_name: string;
  fund_health_score: number;
  category_rank: number;
  category_percentile: number;
  return_1y?: number;
  alpha_1y?: number;
  max_drawdown_1y?: number;
  volatility_1y?: number;
}

export interface CategoryRankingResponse {
  as_of_date: string;
  category: string;
  rankings: CategoryRankingItem[];
}

export interface PipelineHealth {
  as_of_date: string;
  latest_nav_date?: string;
  latest_score_date?: string;
  latest_alert_date?: string;
  last_run_status: string;
  last_run_duration_seconds?: number;
  schemes_processed: number;
  alerts_generated: number;
}

export interface BenchmarkHistory {
  benchmark_code: string;
  benchmark_name: string;
  data: Array<{ date: string; value: number }>;
}

export interface MacroData {
  data: Record<string, Array<{ date: string; value: number }>>;
}