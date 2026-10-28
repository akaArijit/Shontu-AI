/**
 * Mock API Service for Standalone Frontend Development
 * Provides realistic mock data for UI testing without backend
 * Enable with: NEXT_PUBLIC_USE_MOCK_API=true
 */

import {
  FundScore,
  FundScoresResponse,
  Alert,
  AlertsResponse,
  AlertSummary,
  MFDSchemeSummary,
  MFDSchemesResponse,
  CategoryRankingItem,
  CategoryRankingResponse,
  PipelineHealth,
  BenchmarkHistory,
  MacroData,
  FundScoresResponse as FundScoresResponseType,
  AlertsResponse as AlertsResponseType,
  AlertSummary as AlertSummaryType,
  MFDSchemesResponse as MFDSchemesResponseType,
  CategoryRankingResponse as CategoryRankingResponseType,
  PipelineHealth as PipelineHealthType,
  BenchmarkHistory as BenchmarkHistoryType,
  MacroData as MacroDataType,
} from '@/types';

// Simulated delay for realistic feel
const DELAY_MS = 300;

const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

// ============================================================
// MOCK DATA GENERATORS
// ============================================================

const SCHEME_CATEGORIES = [
  'Large Cap', 'Flexi Cap', 'Mid Cap', 'Small Cap',
  'Large & Mid Cap', 'ELSS', 'Hybrid Aggressive',
  'Debt - Ultra Short Duration', 'International - US',
  'Sectoral - Banking', 'Sectoral - IT', 'Sectoral - Pharma',
];

const AMCs = [
  'HDFC Mutual Fund', 'ICICI Prudential MF', 'SBI Mutual Fund',
  'Nippon India MF', 'Kotak Mutual Fund', 'Axis Mutual Fund',
  'UTI Mutual Fund', 'Aditya Birla Sun Life MF', 'DSP Mutual Fund',
  'PPFAS Mutual Fund', 'Mirae Asset MF', 'Tata Mutual Fund',
];

const BENCHMARKS = [
  { code: 'NIFTY100_TRI', name: 'Nifty 100 TRI' },
  { code: 'NIFTY500_TRI', name: 'Nifty 500 TRI' },
  { code: 'NIFTY_MIDCAP150_TRI', name: 'Nifty Midcap 150 TRI' },
  { code: 'NIFTY_SMALLCAP250_TRI', name: 'Nifty Smallcap 250 TRI' },
  { code: 'NIFTY_LARGEMIDCAP250_TRI', name: 'Nifty LargeMidcap 250 TRI' },
  { code: 'CRISIL_HYBRID_35_65', name: 'CRISIL Hybrid 35+65' },
  { code: 'CRISIL_SHORT_TERM_BOND', name: 'CRISIL Short Term Bond Index' },
  { code: 'SP500_TRI', name: 'S&P 500 TRI' },
  { code: 'NIFTY_BANK_TRI', name: 'Nifty Bank TRI' },
  { code: 'NIFTY_IT_TRI', name: 'Nifty IT TRI' },
];

const ALERT_TYPES = [
  { type: 'underperform_3m', label: 'Underperf 3M', severity: 'medium' as const },
  { type: 'underperform_6m', label: 'Underperf 6M', severity: 'high' as const },
  { type: 'below_top25_category', label: 'Below Top 25%', severity: 'medium' as const },
  { type: 'below_top50_category', label: 'Below Top 50%', severity: 'high' as const },
  { type: 'rank_decline', label: 'Rank Decline', severity: 'medium' as const },
  { type: 'benchmark_deviation', label: 'Bench Deviation', severity: 'low' as const },
  { type: 'high_drawdown', label: 'High Drawdown', severity: 'medium' as const },
  { type: 'high_volatility', label: 'High Volatility', severity: 'low' as const },
  { type: 'consecutive_underperf', label: 'Consec. Underperf', severity: 'medium' as const },
];

// Generate deterministic pseudo-random values
function seededRandom(seed: string): number {
  let hash = 0;
  for (let i = 0; i < seed.length; i++) {
    hash = ((hash << 5) - hash) + seed.charCodeAt(i);
    hash |= 0;
  }
  return (Math.abs(hash) % 10000) / 10000;
}

function generateScheme(seed: string, index: number): MFDSchemeSummary {
  const rand = seededRandom(seed);
  const category = SCHEME_CATEGORIES[Math.floor(seededRandom(seed + 'cat') * SCHEME_CATEGORIES.length)];
  const amc = AMCs[Math.floor(seededRandom(seed + 'amc') * AMCs.length)];
  const benchmark = BENCHMARKS[Math.floor(seededRandom(seed + 'bench') * BENCHMARKS.length)];
  const score = Math.floor(20 + seededRandom(seed + 'score') * 75);
  const percentile = Math.floor(seededRandom(seed + 'pctl') * 100);
  const rank = Math.floor(1 + seededRandom(seed + 'rank') * 50);

  return {
    scheme_code: `SCHEME_${String(index + 1).padStart(3, '0')}`,
    scheme_name: `${amc.split(' ')[0]} ${category} Fund`,
    amc,
    category,
    benchmark_name: benchmark.name,
    fund_health_score: score,
    category_rank: rank,
    category_percentile: percentile,
    return_1y: (seededRandom(seed + 'ret1y') - 0.3) * 0.5,
    alpha_1y: (seededRandom(seed + 'alpha') - 0.5) * 0.1,
    max_drawdown_1y: 0.05 + seededRandom(seed + 'dd') * 0.25,
    volatility_1y: 0.1 + seededRandom(seed + 'vol') * 0.2,
    consecutive_underperf_months: Math.floor(seededRandom(seed + 'streak') * 8),
    high_alerts: Math.floor(seededRandom(seed + 'halert') * 3),
    medium_alerts: Math.floor(seededRandom(seed + 'malert') * 3),
    low_alerts: Math.floor(seededRandom(seed + 'lalert') * 3),
  };
}

function generateAlert(scheme: MFDSchemeSummary, index: number): Alert {
  const alertType = ALERT_TYPES[Math.floor(seededRandom(scheme.scheme_code + 'alert' + index) * ALERT_TYPES.length)];
  const daysAgo = Math.floor(Math.random() * 30);
  const date = new Date();
  date.setDate(date.getDate() - daysAgo);

  return {
    alert_id: `alert_${scheme.scheme_code}_${index}`,
    scheme_code: scheme.scheme_code,
    scheme_name: scheme.scheme_name,
    category: scheme.category,
    alert_type: alertType.type,
    severity: alertType.severity,
    triggered_on: new Date(Date.now() - daysAgo * 86400000).toISOString().split('T')[0],
    resolved_on: undefined,
    details: {
      rule_id: alertType.type,
      condition: `Simulated condition for ${alertType.type}`,
      feature_values: { value: Math.random() * 100 },
    },
  };
}

// ============================================================
// PRE-GENERATED MOCK DATA
// ============================================================

const MOCK_SCHEMES = Array.from({ length: 150 }, (_, i) => generateScheme(`scheme_${i}`, i));
const MOCK_ALERTS = MOCK_SCHEMES.flatMap(s => Array.from({ length: Math.floor(Math.random() * 3) }, (_, i) => generateAlert(s, i)));

// Generate category rankings
const CATEGORY_RANKINGS: Record<string, CategoryRankingItem[]> = {};
SCHEME_CATEGORIES.forEach(cat => {
  CATEGORY_RANKINGS[cat] = MOCK_SCHEMES
    .filter(s => s.category === cat)
    .sort((a, b) => b.fund_health_score - a.fund_health_score)
    .map((s, i) => ({ ...s, category_rank: i + 1, category_percentile: Math.floor((1 - i / Math.max(1, MOCK_SCHEMES.filter(s => s.category === cat).length - 1)) * 100) }));
});

const MOCK_PIPELINE_HEALTH: PipelineHealth = {
  as_of_date: new Date().toISOString().split('T')[0],
  latest_nav_date: new Date(Date.now() - 86400000).toISOString().split('T')[0],
  latest_score_date: new Date().toISOString().split('T')[0],
  latest_alert_date: new Date().toISOString().split('T')[0],
  last_run_status: 'healthy',
  last_run_duration_seconds: 1245,
  schemes_processed: 148,
  alerts_generated: 23,
  started_at: new Date(Date.now() - 1245000).toISOString(),
};

const MOCK_BENCHMARK_HISTORY: Record<string, BenchmarkHistory> = {};
BENCHMARKS.forEach(b => {
  MOCK_BENCHMARK_HISTORY[b.code] = {
    benchmark_code: b.code,
    benchmark_name: b.name,
    data: Array.from({ length: 252 }, (_, i) => ({
      date: new Date(Date.now() - (251 - i) * 86400000).toISOString().split('T')[0],
      value: Math.floor(10000 + Math.random() * 5000 + i * 10),
    })),
  };
});

const MOCK_MACRO_DATA: MacroData = {
  data: {
    repo_rate: Array.from({ length: 12 }, (_, i) => ({
      date: new Date(Date.now() - (11 - i) * 30 * 86400000).toISOString().split('T')[0],
      value: 6.5 + (Math.random() - 0.5) * 0.5,
    })),
    cpi: Array.from({ length: 12 }, (_, i) => ({
      date: new Date(Date.now() - (11 - i) * 30 * 86400000).toISOString().split('T')[0],
      value: 5.0 + (Math.random() - 0.5) * 1.5,
    })),
    usd_inr: Array.from({ length: 30 }, (_, i) => ({
      date: new Date(Date.now() - (29 - i) * 86400000).toISOString().split('T')[0],
      value: 83.0 + (Math.random() - 0.5) * 2,
    })),
    india_vix: Array.from({ length: 30 }, (_, i) => ({
      date: new Date(Date.now() - (29 - i) * 86400000).toISOString().split('T')[0],
      value: 12 + Math.random() * 8,
    })),
  },
};

// ============================================================
// MOCK API IMPLEMENTATION
// ============================================================

function filterSchemes(schemes: MFDSchemeSummary[], params: Record<string, unknown>) {
  let result = [...schemes];

  if (params.category) {
    result = result.filter(s => s.category === params.category);
  }
  if (params.minScore) {
    result = result.filter(s => s.fund_health_score >= Number(params.minScore));
  }
  if (params.maxScore) {
    result = result.filter(s => s.fund_health_score <= Number(params.maxScore));
  }
  if (params.hasAlerts) {
    result = result.filter(s => s.high_alerts + s.medium_alerts + s.low_alerts > 0);
  }
  if (params.search) {
    const search = String(params.search).toLowerCase();
    result = result.filter(s =>
      s.scheme_name.toLowerCase().includes(search) ||
      s.scheme_code.toLowerCase().includes(search) ||
      s.amc.toLowerCase().includes(search)
    );
  }
  return result;
}

function sortSchemes(schemes: MFDSchemeSummary[], sortConfig: { key: string; direction: 'asc' | 'desc' }) {
  return [...schemes].sort((a, b) => {
    const aVal = a[sortConfig.key as keyof MFDSchemeSummary];
    const bVal = b[sortConfig.key as keyof MFDSchemeSummary];
    if (aVal === undefined || bVal === undefined) return 0;
    if (typeof aVal === 'string' && typeof bVal === 'string') {
      return sortConfig.direction === 'asc' ? aVal.localeCompare(bVal) : bVal.localeCompare(aVal);
    }
    if (typeof aVal === 'number' && typeof bVal === 'number') {
      return sortConfig.direction === 'asc' ? aVal - bVal : bVal - aVal;
    }
    return 0;
  });
}

export const mockApi = {
  // Schemes
  async getSchemes(params: Record<string, unknown> = {}): Promise<MFDSchemesResponseType> {
    await delay(DELAY_MS);
    let schemes = filterSchemes(MOCK_SCHEMES, params);

    if (params.sortBy) {
      schemes = sortSchemes(schemes, { key: String(params.sortBy), direction: (params.sortOrder as 'asc' | 'desc') || 'desc' });
    }

    const page = Number(params.offset || 0);
    const limit = Number(params.limit || 100);
    const paginated = schemes.slice(page, page + limit);

    return {
      as_of_date: new Date().toISOString().split('T')[0],
      total: schemes.length,
      limit,
      offset: page,
      schemes: paginated,
    };
  },

  async getScheme(schemeCode: string): Promise<MFDSchemeSummary> {
    await delay(DELAY_MS);
    const scheme = MOCK_SCHEMES.find(s => s.scheme_code === schemeCode);
    if (!scheme) throw new Error(`Scheme ${schemeCode} not found`);
    return scheme;
  },

  // Scores
  async getScores(params: Record<string, unknown> = {}): Promise<FundScoresResponseType> {
    await delay(DELAY_MS);
    let schemes = filterSchemes(MOCK_SCHEMES, params);

    const scores: FundScore[] = schemes.map(s => ({
      scheme_code: s.scheme_code,
      scheme_name: s.scheme_name,
      category: s.category,
      amc: s.amc,
      benchmark_name: s.benchmark_name,
      fund_health_score: s.fund_health_score,
      category_rank: s.category_rank,
      category_percentile: s.category_percentile,
      breakdown: [
        { component: 'benchmark_outperformance', points: Math.floor(Math.random() * 30), max_points: 30, reason: 'Beat benchmark', raw_value: Math.random() * 0.1 },
        { component: 'category_ranking', points: Math.floor(Math.random() * 20), max_points: 20, reason: 'Good rank', raw_value: Math.random() * 100 },
        { component: 'consistency_of_returns', points: Math.floor(Math.random() * 20), max_points: 20, reason: 'Consistent', raw_value: Math.random() * 10 },
        { component: 'drawdown_control', points: Math.floor(Math.random() * 15), max_points: 15, reason: 'Good DD control', raw_value: Math.random() * 0.2 },
        { component: 'volatility_adjusted', points: Math.floor(Math.random() * 15), max_points: 15, reason: 'Moderate vol', raw_value: Math.random() * 0.2 },
      ],
      penalty: Math.floor(Math.random() * 10),
      scoring_config_version: '1.0',
      as_of_date: new Date().toISOString().split('T')[0],
    }));

    const page = Number(params.offset || 0);
    const limit = Number(params.limit || 100);
    const paginated = scores.slice(Number(params.offset || 0), Number(params.offset || 0) + limit);

    return {
      as_of_date: new Date().toISOString().split('T')[0],
      total: scores.length,
      limit,
      offset: page,
      scores: paginated,
    };
  },

  async getScore(schemeCode: string): Promise<FundScore> {
    await delay(DELAY_MS);
    const scheme = MOCK_SCHEMES.find(s => s.scheme_code === schemeCode);
    if (!scheme) throw new Error(`Scheme ${schemeCode} not found`);
    return {
      scheme_code: scheme.scheme_code,
      scheme_name: scheme.scheme_name,
      category: scheme.category,
      amc: scheme.amc,
      benchmark_name: scheme.benchmark_name,
      fund_health_score: scheme.fund_health_score,
      category_rank: scheme.category_rank,
      category_percentile: scheme.category_percentile,
      breakdown: [
        { component: 'benchmark_outperformance', points: Math.floor(Math.random() * 30), max_points: 30, reason: 'Beat benchmark', raw_value: Math.random() * 0.1 },
        { component: 'category_ranking', points: Math.floor(Math.random() * 20), max_points: 20, reason: 'Good rank', raw_value: Math.random() * 100 },
        { component: 'consistency_of_returns', points: Math.floor(Math.random() * 20), max_points: 20, reason: 'Consistent', raw_value: Math.random() * 10 },
        { component: 'drawdown_control', points: Math.floor(Math.random() * 15), max_points: 15, reason: 'Good DD control', raw_value: Math.random() * 0.2 },
        { component: 'volatility_adjusted', points: Math.floor(Math.random() * 15), max_points: 15, reason: 'Moderate vol', raw_value: Math.random() * 0.2 },
      ],
      penalty: Math.floor(Math.random() * 10),
      scoring_config_version: '1.0',
      as_of_date: new Date().toISOString().split('T')[0],
    };
  },

  async getLatestScores(params: Record<string, unknown> = {}) {
    return this.getScores({ ...params, as_of_date: new Date().toISOString().split('T')[0] });
  },

  // Alerts
  async getAlerts(params: Record<string, unknown> = {}): Promise<AlertsResponseType> {
    await delay(DELAY_MS);
    let alerts = [...MOCK_ALERTS];

    if (params.unresolved_only) {
      alerts = alerts.filter(a => !a.resolved_on);
    }
    if (params.severities) {
      const severities = String(params.severities).split(',');
      alerts = alerts.filter(a => severities.includes(a.severity));
    }
    if (params.alert_types) {
      const types = String(params.alert_types).split(',');
      alerts = alerts.filter(a => types.includes(a.alert_type));
    }
    if (params.scheme_codes) {
      const codes = String(params.scheme_codes).split(',');
      alerts = alerts.filter(a => codes.includes(a.scheme_code));
    }

    const page = Number(params.offset || 0);
    const limit = Number(params.limit || 100);
    const paginated = alerts.slice(page, page + limit);

    return {
      as_of_date: new Date().toISOString().split('T')[0],
      total: alerts.length,
      limit,
      offset: page,
      alerts: paginated,
    };
  },

  async getAlertsSummary(): Promise<AlertSummaryType[]> {
    await delay(DELAY_MS);
    return [
      { alert_type: 'underperform_3m', severity: 'medium', count: 12, schemes_affected: 10, latest_triggered: new Date().toISOString().split('T')[0] },
      { alert_type: 'underperform_6m', severity: 'high', count: 3, schemes_affected: 3, latest_triggered: new Date().toISOString().split('T')[0] },
      { alert_type: 'below_top25_category', severity: 'medium', count: 18, schemes_affected: 15, latest_triggered: new Date().toISOString().split('T')[0] },
      { alert_type: 'below_top50_category', severity: 'high', count: 8, schemes_affected: 8, latest_triggered: new Date().toISOString().split('T')[0] },
      { alert_type: 'rank_decline', severity: 'medium', count: 15, schemes_affected: 12, latest_triggered: new Date().toISOString().split('T')[0] },
      { alert_type: 'benchmark_deviation', severity: 'low', count: 22, schemes_affected: 18, latest_triggered: new Date().toISOString().split('T')[0] },
      { alert_type: 'high_drawdown', severity: 'medium', count: 7, schemes_affected: 7, latest_triggered: new Date().toISOString().split('T')[0] },
      { alert_type: 'high_volatility', severity: 'low', count: 11, schemes_affected: 9, latest_triggered: new Date().toISOString().split('T')[0] },
      { alert_type: 'consecutive_underperf', severity: 'medium', count: 9, schemes_affected: 8, latest_triggered: new Date().toISOString().split('T')[0] },
    ];
  },

  async resolveAlert(alertId: string) {
    await delay(DELAY_MS);
    return { success: true, alert_id: alertId };
  },

  async dismissAlert(alertId: string, reason: string) {
    await delay(DELAY_MS);
    return { success: true, alert_id: alertId };
  },

  async bulkResolveAlerts(alertIds: string[], resolvedBy: string) {
    await delay(DELAY_MS);
    return { success: true, resolved_count: alertIds.length };
  },

  async bulkDismissAlerts(alertIds: string[], dismissedBy: string, reason: string) {
    await delay(DELAY_MS);
    return { success: true, dismissed_count: alertIds.length };
  },

  // Rankings
  async getCategoryRankings(category: string, metric = 'score'): Promise<CategoryRankingResponseType> {
    await delay(DELAY_MS);
    const rankings = CATEGORY_RANKINGS[category] || [];
    const categoryLength = rankings.length;
    return {
      as_of_date: new Date().toISOString().split('T')[0],
      category,
      rankings: rankings.map((r, i) => ({
        ...r,
        category_rank: r.category_rank || i + 1,
        category_percentile: r.category_percentile ?? Math.floor((1 - i / Math.max(1, categoryLength - 1)) * 100),
      })),
    };
  },

  async getAllCategoryRankings() {
    await delay(DELAY_MS);
    const asOfDate = new Date().toISOString().split('T')[0];
    return Object.entries(CATEGORY_RANKINGS).map(([category, rankings]) => ({
      as_of_date: asOfDate,
      category,
      rankings: rankings.map((r, i) => ({
        ...r,
        category_rank: r.category_rank || i + 1,
        category_percentile: r.category_percentile ?? Math.floor((1 - i / Math.max(1, rankings.length - 1)) * 100),
      })),
    }));
  },

  // Health & Meta
  async getHealth(): Promise<PipelineHealthType> {
    await delay(DELAY_MS);
    return MOCK_PIPELINE_HEALTH;
  },

  async getScoringConfig() {
    await delay(DELAY_MS);
    return {
      version: '1.0',
      effective_date: '2024-01-01',
      components: {
        benchmark_outperformance: { weight: 0.30, max_points: 30 },
        category_ranking: { weight: 0.20, max_points: 20 },
        consistency_of_returns: { weight: 0.20, max_points: 20 },
        drawdown_control: { weight: 0.15, max_points: 15 },
        volatility_adjusted: { weight: 0.15, max_points: 15 },
      },
      penalty_per_month: 2.0,
      penalty_cap: 20.0,
    };
  },

  async getRulesConfig() {
    await delay(DELAY_MS);
    return {
      alert_rules: [
        { id: 'underperform_3m', condition: 'consecutive_underperf_months >= 3', severity: 'medium', enabled: true, category_overrides: {} },
        { id: 'underperform_6m', condition: 'consecutive_underperf_months >= 6', severity: 'high', enabled: true, category_overrides: {} },
        { id: 'below_top25_category', condition: 'category_percentile_1y < 75', severity: 'medium', enabled: true, category_overrides: {} },
        { id: 'below_top50_category', condition: 'category_percentile_1y < 50', severity: 'high', enabled: true, category_overrides: {} },
        { id: 'rank_decline', condition: 'category_rank_1y - category_rank_3m > 10', severity: 'medium', enabled: true, category_overrides: {} },
        { id: 'benchmark_deviation', condition: '|alpha_1y| > 0.05', severity: 'low', enabled: true, category_overrides: { 'Small Cap': 10, 'Mid Cap': 8 } },
        { id: 'high_drawdown', condition: 'max_drawdown_1y > 0.20', severity: 'medium', enabled: true, category_overrides: {} },
        { id: 'high_volatility', condition: 'volatility_1y > 0.25', severity: 'low', enabled: true, category_overrides: {} },
        { id: 'consecutive_underperf', condition: 'consecutive_underperf_months >= 4', severity: 'medium', enabled: true, category_overrides: {} },
      ],
    };
  },

  // Benchmarks & Macro
  async getBenchmarkHistory(benchmarkCode: string, fromDate?: string, toDate?: string): Promise<BenchmarkHistoryType> {
    await delay(DELAY_MS);
    const data = MOCK_BENCHMARK_HISTORY[benchmarkCode];
    if (!data) throw new Error('Benchmark not found');

    let dataFiltered = data.data;
    if (fromDate) dataFiltered = dataFiltered.filter(d => d.date >= fromDate);
    if (toDate) dataFiltered = dataFiltered.filter(d => d.date <= toDate);

    return { ...data, data: dataFiltered };
  },

  async getMacroData(indicators = 'repo_rate,cpi,usd_inr,india_vix'): Promise<MacroDataType> {
    await delay(DELAY_MS);
    const requested = indicators.split(',');
    const filteredData: Record<string, any[]> = {};
    requested.forEach(key => {
      if (MOCK_MACRO_DATA.data[key]) filteredData[key] = MOCK_MACRO_DATA.data[key];
    });
    return { data: filteredData };
  },

  // CSV Upload (mock)
  async uploadSchemeMasterCSV(file: File, dryRun = false) {
    await delay(1000);
    return {
      success: true,
      message: 'CSV processed successfully (mock)',
      total_rows: 10,
      valid_rows: 10,
      invalid_rows: 0,
      errors: [],
      preview: MOCK_SCHEMES.slice(0, 3).map(s => ({ scheme_code: s.scheme_code, scheme_name: s.scheme_name, category: s.category })),
    };
  },

  async downloadSchemeMaster() {
    await delay(500);
    const headers = 'scheme_code,scheme_name,amc,category,sub_category,benchmark_index,fund_manager,expense_ratio,aum,inception_date,is_active,short_name\n';
    const rows = MOCK_SCHEMES.slice(0, 5).map(s =>
      `${s.scheme_code},${s.scheme_name},${s.amc},${s.category},,${s.benchmark_name},,${(Math.random()*2).toFixed(2)},${Math.floor(Math.random()*50000)},2020-01-01,true,${s.scheme_name.split(' ').slice(0,2).join(' ')}`
    ).join('\n');
    return new Blob([headers + rows], { type: 'text/csv' });
  },

  async uploadBenchmarkMappings(file: File, dryRun = false) {
    await delay(500);
    return {
      success: true,
      message: 'Benchmark mappings uploaded (mock)',
      total_rows: 5,
      valid_rows: 5,
      invalid_rows: 0,
      errors: [],
      preview: [],
    };
  },

  async downloadBenchmarkTemplate() {
    await delay(500);
    const headers = 'scheme_code,scheme_name,amc,category,sub_category,benchmark_index,fund_manager,expense_ratio,aum,inception_date,is_active,short_name\n';
    const rows = MOCK_SCHEMES.slice(0, 3).map(s =>
      `${s.scheme_code},${s.scheme_name},${s.amc},${s.category},,,,${(Math.random()*2).toFixed(2)},${Math.floor(Math.random()*50000)},2020-01-01,true,${s.scheme_name.split(' ').slice(0,2).join(' ')}`
    ).join('\n');
    return new Blob([headers + rows], { type: 'text/csv' });
  },
};

// Check if mock API should be used
export function useMockApi(): boolean {
  return process.env.NEXT_PUBLIC_USE_MOCK_API === 'true' || typeof window !== 'undefined' && localStorage.getItem('use_mock_api') === 'true';
}

export { MOCK_SCHEMES, MOCK_ALERTS, MOCK_PIPELINE_HEALTH, CATEGORY_RANKINGS, MOCK_BENCHMARK_HISTORY, MOCK_MACRO_DATA };