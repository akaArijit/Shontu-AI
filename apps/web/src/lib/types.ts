export type Severity = "error" | "warning" | "info" | string;

export interface ImportIssue {
  id?: number;
  file_type: string;
  row_number: number | null;
  field: string | null;
  message: string;
  severity: Severity;
}

export interface SectionDetails {
  file_type: string;
  sheet: string | null;
  header_row: number | null;
  mapping: Record<string, string>;
  headers: string[];
  unmapped_columns: string[];
  ignored_sensitive_columns: string[];
  missing_required: string[];
  duplicate_targets: string[];
  headerless?: boolean;
  layout_warning?: string | null;
  source_kind?: string;
  not_supplied?: boolean;
}

export interface FileInfo {
  name: string;
  size: number;
  sha256: string;
}

export interface PreviewSampleFolio {
  client_name: string;
  folio_number: string;
  scheme_name: string;
  benchmark_name: string;
  benchmark_status: string;
  match_status: string;
  aum: string | null;
}

export interface FileSkipReason {
  key: string;
  label: string;
  count: number;
}

export interface FileReport {
  file_type: "clients" | "folios" | "portfolio" | "transactions" | string;
  label: string;
  supplied: boolean;
  rows_read: number;
  imported_rows: number;
  matched_rows: number | null;
  unmatched_rows: number | null;
  skipped_rows: number;
  blank_rows: number;
  total_rows: number;
  duplicate_rows: number;
  invalid_date_rows: number;
  invalid_number_rows: number;
  header_ok: boolean;
  message: string;
  reasons: FileSkipReason[];
}

export interface ClientMatchingFileSummary {
  total: number;
  matched: number | null;
  unmatched: number | null;
}

export interface ClientMatchingSummary {
  status: "matched" | "review" | "no_clients" | string;
  message: string;
  clients: number;
  folios: ClientMatchingFileSummary;
  portfolio: ClientMatchingFileSummary;
  transactions: ClientMatchingFileSummary | null;
}

export interface ExportRunFile {
  file_name: string;
  dates: string[];
  latest_date: string | null;
}

export interface ExportRunCheck {
  status: "consistent" | "review" | "unconfirmed" | string;
  message: string;
  report_date: string | null;
  files: Record<string, ExportRunFile>;
}

export interface PreviewResponse {
  import_id: string;
  created_at: string;
  status: string;
  report_date: string | null;
  report_date_format: string | null;
  transactions_supplied?: boolean;
  files: {
    clients: FileInfo;
    folios: FileInfo;
    portfolio: FileInfo;
    transactions: FileInfo | null;
  };
  detected_columns: {
    clients: SectionDetails;
    folios: SectionDetails;
    portfolio: SectionDetails;
    transactions: SectionDetails;
  };
  counts: {
    client_rows: number;
    clients_imported: number;
    clients_skipped: number;
    folio_rows: number;
    folios_imported: number;
    folios_skipped: number;
    portfolio_rows: number;
    portfolio_imported: number;
    portfolio_skipped: number;
    transaction_rows: number;
    transactions_imported: number;
    transaction_skipped: number;
    transactions_unmatched: number;
    unknown_transactions: number;
    switch_pairs: number;
    switch_reviews: number;
    schemes: number;
    needs_review: number;
    unmatched_folios: number;
    unmatched_portfolio_rows: number;
    rows_read: number;
    blank_rows: number;
    total_rows: number;
    duplicate_rows: number;
    invalid_date_rows: number;
    invalid_number_rows: number;
    reconciliation_warnings: number;
    issues: number;
    errors: number;
    warnings: number;
  };
  file_reports: Record<string, FileReport>;
  client_matching: ClientMatchingSummary;
  export_run: ExportRunCheck;
  issues: ImportIssue[];
  issue_count: number;
  issues_truncated: boolean;
  preview_rows_omitted?: boolean;
  preview_issues_truncated?: boolean;
  warnings: string[];
  can_confirm: boolean;
  sample_folios: PreviewSampleFolio[];
}

export interface ConfirmResponse {
  import_id: string;
  batch_id: number;
  report_date: string;
  imported: {
    clients: number;
    folios: number;
    portfolio_rows: number;
    transactions: number;
    schemes: number;
    needs_review: number;
    switch_pairs: number;
    switch_reviews: number;
  };
  skipped: {
    clients: number;
    folios: number;
    portfolio_rows: number;
    transactions: number;
  };
  unmatched: {
    folios: number;
    portfolio_rows: number;
    transactions: number;
  };
  reconciliation_warnings: number;
  issues: number;
  warnings: string[];
}

export type ReconciliationStatus =
  | "matched"
  | "mismatch"
  | "partial"
  | "not_available"
  | "no_folios";

export interface ClientSummary {
  id: number;
  name: string;
  iwell_code: string | null;
  iwell_code_2: string | null;
  app_code: string | null;
  first_investment_date: string | null;
  folio_count: number;
  folio_aum_total: number | null;
  folio_aum_missing_count: number;
  current_value: number | null;
  purchase_value: number | null;
  gain: number | null;
  absolute_return: number | null;
  cagr: number | null;
  avg_holding_days: number | null;
  valuation_date: string | null;
  reconciliation_status: ReconciliationStatus;
  difference: number | null;
  match_status: string;
  notes: string[];
}

export interface FolioRow {
  id: number;
  client_id: number | null;
  client_name: string;
  client_iwell_code: string | null;
  folio_number: string;
  scheme_name: string;
  folio_type: string;
  units: number | null;
  aum: number | null;
  value_date: string | null;
  benchmark_name: string;
  benchmark_status: string;
  match_status: string;
  match_note: string | null;
  invested_amount: number | null;
  gross_invested: number | null;
  net_invested: number | null;
  redemption_proceeds: number | null;
  switch_out_proceeds: number | null;
  absolute_return: number | null;
  holding_period: number | null;
  first_investment_date: string | null;
  xirr: number | null;
  benchmark_xirr: number | null;
  benchmark_return: number | null;
  benchmark_return_type: "absolute" | "xirr" | null;
  folio_comparison_return: number | null;
  benchmark_difference: number | null;
  benchmark_current_value: number | null;
  benchmark_comparison_status: string;
  benchmark_comparison_method: "point_to_point" | "cash_flow_xirr" | null;
  benchmark_comparison_note: string | null;
  benchmark_missing_dates: string[];
  benchmark_missing_date_count: number;
  transaction_count: number;
  switch_review_count: number;
  missing_date_count: number;
  missing_amount_count: number;
  unknown_transaction_count: number;
  notes: string[];
}

export interface UnmatchedPortfolioRow {
  id: number;
  client_name: string;
  source_iwell_code: string | null;
  current_value: number | null;
  purchase_value: number | null;
  gain: number | null;
  absolute_return: number | null;
  cagr: number | null;
  valuation_date: string;
  match_status: string;
  match_note: string | null;
}

export interface ReconciliationRow {
  client_id: number;
  client_name: string;
  iwell_code: string | null;
  folio_count: number;
  folio_aum_total: number | null;
  folio_aum_missing_count: number;
  client_current_value: number | null;
  difference: number | null;
  status: ReconciliationStatus;
}

export interface TotalReconciliation {
  report_total: number | null;
  sum_of_client_rows: number | null;
  difference: number | null;
  status: "matched" | "mismatch" | "not_available";
}

export interface DashboardSummary {
  clients: number;
  folios: number;
  portfolio_rows: number;
  total_folio_aum: number | null;
  total_current_value: number | null;
  total_purchase_value: number | null;
  total_gross_invested: number | null;
  total_net_invested: number | null;
  unmatched_folio_aum: number | null;
  unmatched_current_value: number | null;
  needs_review: number;
  unmatched_folios: number;
  unmatched_portfolio_rows: number;
  transactions: number;
  transactions_unmatched: number;
  unknown_transactions: number;
  switch_reviews: number;
  missing_transaction_dates: number;
  missing_transaction_amounts: number;
  xirr_available: number;
  benchmark_comparisons_available: number;
  benchmark_levels_missing: number;
  benchmark_reviewed: number;
  benchmark_mapping_missing: number;
  benchmark_mapping_needs_review: number;
  benchmark_point_to_point: number;
  benchmark_cash_flow: number;
  reconciliation_warnings: number;
  partial_reconciliation: number;
  missing_folio_aum: number;
  missing_current_value: number;
  issues: number;
  errors: number;
  warnings: number;
}

export interface DashboardResponse {
  summary: DashboardSummary;
  clients: ClientSummary[];
  folios: FolioRow[];
  unmatched_portfolio: UnmatchedPortfolioRow[];
  reconciliation: ReconciliationRow[];
  total_reconciliation: TotalReconciliation | null;
  issues: ImportIssue[];
  meta: {
    has_data: boolean;
    valuation_date: string | null;
    benchmark_data: string;
    folio_value_source: string;
    client_value_source: string;
    return_source: string;
    folio_invested_amount: string;
    folio_absolute_return: string;
    folio_holding_period: string;
    folio_xirr: string;
    transaction_file_name: string | null;
    batch: {
      id: number;
      import_id: string;
      client_file_name: string;
      folios_file_name: string;
      portfolio_file_name: string;
      transaction_file_name?: string | null;
      confirmed_at: string;
      report_date: string;
    } | null;
  };
}

export type CoverageStatus =
  | "needs_mapping"
  | "needs_review"
  | "no_transactions"
  | "no_levels"
  | "missing_dates"
  | "covered"
  | "no_required_dates"
  | "unknown"
  | string;

export interface BenchmarkCoverageSummary {
  schemes_total: number;
  schemes_needs_mapping: number;
  schemes_needs_review: number;
  schemes_covered: number;
  schemes_missing_dates: number;
  schemes_no_levels: number;
  schemes_no_transactions: number;
  series_total: number;
  series_covered: number;
  series_missing_dates: number;
  series_no_required_dates: number;
  valuation_date: string | null;
  valuation_date_missing_in: string[];
  first_transaction_missing_in: string[];
}

export interface BenchmarkCoverageSeries {
  benchmark_name: string;
  benchmark_key: string;
  coverage_status: CoverageStatus;
  comparison_method: "point_to_point" | "cash_flow_xirr" | null;
  scheme_names: string[];
  scheme_count: number;
  folio_count: number;
  needs_review_count: number;
  first_transaction_date: string | null;
  required_date_count: number;
  available_date_count: number;
  missing_date_count: number;
  missing_dates: string[];
  covers_first_transaction: boolean | null;
  covers_valuation_date: boolean | null;
  covers_all_comparison_dates: boolean | null;
  available_first_date: string | null;
  available_last_date: string | null;
}

export interface BenchmarkCoverageResponse {
  summary: BenchmarkCoverageSummary;
  schemes: Array<Record<string, unknown>>;
  series: BenchmarkCoverageSeries[];
}

export interface BenchmarkMappingItem {
  scheme_id: number;
  scheme_name: string;
  normalized_scheme_name: string;
  benchmark_name: string;
  review_status: "reviewed" | "needs_review" | "needs_mapping" | string;
  source: string;
  folio_count: number;
  suggested_benchmark: string | null;
  suggestion_keyword: string | null;
  suggestion_source: string | null;
  suggestion_match_type: "category" | "fund_house" | "abbreviation" | "other" | null;
  suggestion_confidence: "high" | "medium" | "low" | null;
  suggestion_reason: string | null;
  level_count: number;
  coverage_status: CoverageStatus;
  coverage_missing_dates: string[];
  coverage_missing_date_count: number;
  coverage_required_date_count: number;
  covers_first_transaction: boolean | null;
  covers_valuation_date: boolean | null;
  covers_all_comparison_dates: boolean | null;
  first_transaction_date: string | null;
  updated_at: string | null;
}

export interface BenchmarkMappingSummary {
  schemes: number;
  reviewed: number;
  needs_review: number;
  unmapped: number;
}

export interface BenchmarkMappingStatusSummary {
  total_schemes: number;
  mapped_schemes: number;
  reviewed_schemes: number;
  needs_review_schemes: number;
  unmapped_schemes: number;
  total_folios: number;
  mapped_folios: number;
  needs_review_folios: number;
  unmapped_folios: number;
  suggested_schemes: number;
  suggested_folios: number;
}

export interface BenchmarkMappingResponse {
  mappings: BenchmarkMappingItem[];
  available_benchmarks: string[];
  summary: BenchmarkMappingSummary;
  status_summary: BenchmarkMappingStatusSummary;
  coverage: BenchmarkCoverageResponse;
}

export interface BenchmarkMappingUpdateResponse {
  mapping: BenchmarkMappingItem;
  summary: BenchmarkMappingSummary;
  status_summary?: BenchmarkMappingStatusSummary;
  available_benchmarks: string[];
  coverage: BenchmarkCoverageResponse;
  folios_moved_out_of_unmapped?: number;
  unmapped_folios?: number;
}

export interface BenchmarkMappingChangeResponse
  extends BenchmarkMappingResponse {
  updated_schemes: number;
  updated_folios: number;
  previous_unmapped_folios: number;
  unmapped_folios: number;
  folios_moved_out_of_unmapped: number;
  accepted_schemes?: number;
  accepted_folios?: number;
}

export interface KeywordMappingPreview {
  keyword: string;
  normalized_keyword: string;
  benchmark_name: string;
  rule: string;
  apply: boolean;
  matched_scheme_count: number;
  matched_folio_count: number;
  matched_unmapped_scheme_count: number;
  matched_unmapped_folio_count: number;
  matched_schemes: BenchmarkMappingItem[];
  can_apply: boolean;
  errors: string[];
  updated_schemes?: number;
  updated_folios?: number;
  previous_unmapped_folios?: number;
  unmapped_folios?: number;
  folios_moved_out_of_unmapped?: number;
  mappings?: BenchmarkMappingItem[];
  summary?: BenchmarkMappingSummary;
  status_summary?: BenchmarkMappingStatusSummary;
  available_benchmarks?: string[];
  coverage?: BenchmarkCoverageResponse;
}

export interface MappingFileIssue {
  row_number: number | null;
  field: string | null;
  message: string;
}

export interface MappingFileChange {
  row_number: number;
  scheme_id: number;
  scheme_name: string;
  current_benchmark: string;
  current_status: string;
  benchmark_name: string;
  action: "map" | "approve" | "unchanged" | string;
  folio_count: number;
}

export interface MappingFilePreview {
  file_name: string;
  detected_format: "csv" | "xlsx" | string;
  sheet_name: string;
  header_row: number;
  row_count: number;
  valid_count: number;
  change_count: number;
  unchanged_count: number;
  skipped_count: number;
  error_count: number;
  warning_count: number;
  issues_truncated: boolean;
  can_apply: boolean;
  errors: MappingFileIssue[];
  warnings: MappingFileIssue[];
  changes: MappingFileChange[];
  summary: {
    valid_rows: number;
    change_rows: number;
    unchanged_rows: number;
    skipped_rows: number;
    errors: number;
    warnings: number;
    schemes_to_update: number;
    folios_affected: number;
    unmapped_folios_affected: number;
  };
  applied?: boolean;
  mappings?: BenchmarkMappingItem[];
  mapping_summary?: BenchmarkMappingSummary;
  status_summary?: BenchmarkMappingStatusSummary;
  available_benchmarks?: string[];
  coverage?: BenchmarkCoverageResponse;
  updated_schemes?: number;
  updated_folios?: number;
  previous_unmapped_folios?: number;
  unmapped_folios?: number;
  folios_moved_out_of_unmapped?: number;
}

export interface BenchmarkLevelSummary {
  benchmark_name: string;
  level_count: number;
  first_date: string;
  last_date: string;
  source_file: string;
  updated_at: string;
}

export interface BenchmarkLevelsResponse {
  summaries: BenchmarkLevelSummary[];
  benchmark_names: string[];
  total_benchmarks: number;
  total_levels: number;
}

export interface BenchmarkLevelIssue {
  row_number: number | null;
  field: string | null;
  message: string;
  severity: Severity;
}

export interface BenchmarkLevelImportResponse {
  file_name: string;
  detected_format: "long" | "wide" | string;
  sheet_name: string;
  header_row: number | null;
  created: number;
  updated: number;
  imported: number;
  skipped: number;
  benchmarks: string[];
  first_date: string;
  last_date: string;
  issues: BenchmarkLevelIssue[];
  warnings: string[];
  summaries: BenchmarkLevelSummary[];
}

export type GraphPerformance =
  | "ahead"
  | "behind"
  | "in_line"
  | "not_available"
  | "needs_review";

export interface BenchmarkGraphFolio {
  id: string;
  folio_id: number;
  client_id: number | null;
  client_name: string;
  folio_number: string;
  scheme_name: string;
  benchmark_name: string;
  benchmark_status: string;
  aum: number | null;
  invested_amount: number | null;
  gross_invested: number | null;
  holding_period: number | null;
  first_investment_date: string | null;
  value_date: string | null;
  absolute_return: number | null;
  xirr: number | null;
  benchmark_return: number | null;
  benchmark_return_type: "absolute" | "xirr" | null;
  benchmark_xirr: number | null;
  folio_comparison_return: number | null;
  benchmark_difference: number | null;
  benchmark_comparison_status: string;
  benchmark_comparison_method: "point_to_point" | "cash_flow_xirr" | null;
  benchmark_comparison_note: string | null;
  benchmark_missing_dates: string[];
  benchmark_missing_date_count: number;
  performance: GraphPerformance;
}

export interface BenchmarkGraphClusterStats {
  folio_count: number;
  ahead: number;
  behind: number;
  in_line: number;
  available: number;
  not_available: number;
  needs_review: number;
  missing_folio_aum: number;
  average_difference: number | null;
  average_folio_return: number | null;
  average_benchmark_return: number | null;
  // Milestone 8B: Cluster-level TRI return fields
  avg_holding_days: number | null;
  benchmark_tri_return: number | null;
  benchmark_tri_return_note: string | null;
  benchmark_return_difference: number | null;
}

export interface BenchmarkGraphCluster {
  id: string;
  name: string;
  normalized_name: string;
  level_count: number;
  review_state:
    | "needs_mapping"
    | "needs_review"
    | "levels_missing"
    | "partial"
    | "ready"
    | "no_comparison"
    | "no_folios"
    | string;
  folios: BenchmarkGraphFolio[];
  stats: BenchmarkGraphClusterStats;
}

export interface BenchmarkGraphResponse {
  summary: {
    benchmarks: number;
    folios: number;
    ahead: number;
    behind: number;
    in_line: number;
    needs_review: number;
    not_available: number;
    missing_folio_aum: number;
  };
  clusters: BenchmarkGraphCluster[];
  meta: {
    has_data: boolean;
    valuation_date: string | null;
    benchmark_data: string;
    source: string;
  };
}

export type BusinessPerformance =
  | "ahead"
  | "behind"
  | "in_line"
  | "not_available"
  | "needs_review";

export interface BusinessReviewFolio extends FolioRow {
  performance: BusinessPerformance;
}

export interface ReviewFilterOption {
  key: string;
  name: string;
  count: number;
}

export interface ReviewBenchmarkOption {
  name: string;
  count: number;
}

export interface QualityFolioItem {
  folio_id: number;
  client_id: number | null;
  client_name: string;
  folio_number: string;
  scheme_name: string;
  benchmark_name: string;
  aum: number | null;
  performance: BusinessPerformance;
  match_status: string;
  benchmark_comparison_status: string;
  note: string;
}

export interface ReviewTransactionIssue {
  folio_id: number;
  client_name: string;
  folio_number: string;
  scheme_name: string;
  missing_date_count: number;
  missing_amount_count: number;
  unknown_transaction_count: number;
  summary: string;
}

export interface ConcentrationItem {
  name: string;
  value: number;
  folio_count: number;
  share: number;
}

export interface ConcentrationClientItem {
  client_id: number;
  name: string;
  value: number;
  folio_count: number;
  share: number;
}

export interface BusinessReviewResponse {
  summary: {
    clients: number;
    folios: number;
    transactions: number;
    ahead: number;
    behind: number;
    in_line: number;
    not_available: number;
    needs_review: number;
    underperforming_value: number | null;
    data_quality_items: number;
    data_quality_groups: number;
    comparisons_available: number;
    comparison_coverage: number;
  };
  attention: {
    folios: BusinessReviewFolio[];
    total_folios: number;
    matching: number;
    filter_options: {
      benchmarks: ReviewBenchmarkOption[];
      clients: ReviewFilterOption[];
    };
    applied_filters: {
      performance: "all" | BusinessPerformance;
      benchmark: string;
      client: string;
      min_current_value: number | null;
      sort: "current_value" | "difference" | "xirr" | "client_name";
      direction: "asc" | "desc";
    };
  };
  data_quality: {
    missing_current_value: QualityFolioItem[];
    missing_benchmark_mapping: QualityFolioItem[];
    mapping_needs_review: QualityFolioItem[];
    missing_benchmark_levels: QualityFolioItem[];
    unmatched_folios: QualityFolioItem[];
    unmatched_portfolio: UnmatchedPortfolioRow[];
    reconciliation_warnings: ReconciliationRow[];
    transaction_issues: ReviewTransactionIssue[];
    counts: {
      missing_current_value: number;
      missing_benchmark_mapping: number;
      mapping_needs_review: number;
      missing_benchmark_levels: number;
      unmatched_folios: number;
      unmatched_portfolio_rows: number;
      reconciliation_warnings: number;
      transaction_issues: number;
    };
    total_items: number;
    groups_with_issues: number;
  };
  concentration: {
    total_folio_value: number;
    total_client_value: number;
    missing_folio_value_folios: number;
    clients_without_current_value: number;
    by_benchmark: ConcentrationItem[];
    top_clients: ConcentrationClientItem[];
    top_schemes: ConcentrationItem[];
  };
  review_status: {
    mappings: BenchmarkMappingSummary;
    comparisons: {
      available: number;
      needs_review: number;
      not_available: number;
      ahead: number;
      behind: number;
      in_line: number;
      coverage_percent: number;
    };
    benchmark_data: {
      series: number;
      levels: number;
      series_names: string[];
    };
    coverage: {
      clients: number;
      folios: number;
      portfolio_rows: number;
      transactions: number;
      xirr_available: number;
      xirr_missing: number;
      folio_value_available: number;
      folio_value_missing: number;
      transactions_unmatched: number;
      unknown_transactions: number;
      missing_transaction_dates: number;
      missing_transaction_amounts: number;
    };
  };
  meta: {
    has_data: boolean;
    valuation_date: string | null;
    benchmark_data: string;
    source: string;
  };
}

/**
 * The subset of folio values shown by the shared detail dialog.  Both the
 * dashboard folio row and a benchmark graph folio node satisfy this shape.
 */
export interface FolioDetail {
  client_name: string;
  folio_number: string;
  scheme_name: string;
  benchmark_name: string;
  benchmark_status: string;
  invested_amount: number | null;
  gross_invested: number | null;
  aum: number | null;
  holding_period: number | null;
  first_investment_date: string | null;
  absolute_return: number | null;
  xirr: number | null;
  benchmark_return: number | null;
  benchmark_return_type: "absolute" | "xirr" | null;
  benchmark_xirr: number | null;
  benchmark_difference: number | null;
  benchmark_comparison_status: string;
  benchmark_comparison_method: "point_to_point" | "cash_flow_xirr" | null;
  benchmark_comparison_note: string | null;
  benchmark_missing_dates?: string[];
  benchmark_missing_date_count?: number;
}
