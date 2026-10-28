import { clsx, type ClassValue } from 'clsx';
import { twMerge } from 'tailwind-merge';

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function formatCurrency(value: number | undefined): string {
  if (value === undefined || value === null) return '—';
  if (value >= 1e7) return `₹${(value / 1e7).toFixed(1)} Cr`;
  if (value >= 1e5) return `₹${(value / 1e5).toFixed(1)} L`;
  return `₹${value.toLocaleString('en-IN')}`;
}

export function formatPercent(value: number | undefined, decimals = 2): string {
  if (value === undefined || value === null) return '—';
  return `${(value * 100).toFixed(decimals)}%`;
}

export function formatNumber(value: number | undefined, decimals = 2): string {
  if (value === undefined || value === null) return '—';
  return value.toFixed(decimals);
}

export function formatRank(rank: number | undefined): string {
  if (!rank) return '—';
  return `#${rank}`;
}

export function formatPercentile(pctl: number | undefined): string {
  if (!pctl && pctl !== 0) return '—';
  return `${pctl.toFixed(1)}th`;
}

export function getScoreColor(score: number): string {
  if (score >= 75) return 'text-success-600 bg-success-50 border-success-200';
  if (score >= 50) return 'text-warning-600 bg-warning-50 border-warning-200';
  return 'text-danger-600 bg-danger-50 border-danger-200';
}

export function getScoreBand(score: number): 'green' | 'yellow' | 'red' {
  if (score >= 75) return 'green';
  if (score >= 50) return 'yellow';
  return 'red';
}

export function getSeverityColor(severity: string): string {
  switch (severity) {
    case 'high': return 'text-danger-600 bg-danger-50 border-danger-200';
    case 'medium': return 'text-warning-600 bg-warning-50 border-warning-200';
    case 'low': return 'text-primary-600 bg-primary-50 border-primary-200';
    default: return 'text-neutral-600 bg-neutral-50 border-neutral-200';
  }
}

export function getSeverityIcon(severity: string) {
  switch (severity) {
    case 'high': return '🔴';
    case 'medium': return '🟡';
    case 'low': return '🔵';
    default: return '⚪';
  }
}

export function getStatusColor(status: string): string {
  switch (status) {
    case 'critical': return 'text-danger-600 bg-danger-50';
    case 'warning': return 'text-warning-600 bg-warning-50';
    case 'watch': return 'text-primary-600 bg-primary-50';
    case 'ok': return 'text-success-600 bg-success-50';
    default: return 'text-neutral-600 bg-neutral-50';
  }
}

export function getStatusDot(status: string): string {
  switch (status) {
    case 'critical': return 'bg-danger-500';
    case 'warning': return 'bg-warning-500';
    case 'watch': return 'bg-primary-500';
    case 'ok': return 'bg-success-500';
    default: return 'bg-neutral-400';
  }
}

export function truncate(str: string, length: number): string {
  if (str.length <= length) return str;
  return str.slice(0, length) + '…';
}

export function formatDate(dateStr: string): string {
  return new Date(dateStr).toLocaleDateString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
  });
}

export function formatDateTime(dateStr: string): string {
  return new Date(dateStr).toLocaleString('en-IN', {
    day: '2-digit',
    month: 'short',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

export function getAlertTypeLabel(type: string): string {
  const labels: Record<string, string> = {
    underperform_3m: 'Underperf 3M',
    underperform_6m: 'Underperf 6M',
    below_top25_category: 'Below Top 25%',
    below_top50_category: 'Below Top 50%',
    rank_decline: 'Rank Decline',
    benchmark_deviation: 'Bench Deviation',
    high_drawdown: 'High Drawdown',
    high_volatility: 'High Volatility',
    consecutive_underperf: 'Consec. Underperf',
  };
  return labels[type] || type;
}

export function getComponentLabel(component: string): string {
  const labels: Record<string, string> = {
    benchmark_outperformance: 'Benchmark Outperformance',
    category_ranking: 'Category Ranking',
    consistency_of_returns: 'Consistency',
    drawdown_control: 'Drawdown Control',
    volatility_adjusted: 'Volatility Adjusted',
  };
  return labels[component] || component;
}