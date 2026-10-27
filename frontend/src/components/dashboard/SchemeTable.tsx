'use client';

import React from 'react';
import { useState, useMemo } from 'react';
import { cn, getScoreColor, getScoreBand, getSeverityColor, getSeverityIcon, formatPercent, formatNumber, getAlertTypeLabel, formatDate, truncate } from '@/lib/utils';
import { MFDSchemeSummary } from '@/types';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { MoreHorizontal, ChevronDown, ChevronUp, ExternalLink, AlertTriangle } from 'lucide-react';

interface SchemeTableProps {
  schemes: MFDSchemeSummary[];
  loading?: boolean;
  onSchemeClick?: (scheme: MFDSchemeSummary) => void;
}

function filterAndSortSchemes(
  schemes: MFDSchemeSummary[],
  filters: { category: string; minScore: string; maxScore: string; hasAlerts: boolean; search: string },
  sortConfig: { key: string; direction: 'asc' | 'desc' }
): MFDSchemeSummary[] {
  let result = schemes.filter((scheme) => {
    if (filters.category && scheme.category !== filters.category) return false;
    if (filters.minScore && scheme.fund_health_score < parseInt(filters.minScore)) return false;
    if (filters.maxScore && scheme.fund_health_score > parseInt(filters.maxScore)) return false;
    if (filters.hasAlerts && (scheme.high_alerts + scheme.medium_alerts + scheme.low_alerts) === 0) return false;
    if (filters.search) {
      const search = filters.search.toLowerCase();
      if (
        !scheme.scheme_name.toLowerCase().includes(search) &&
        !scheme.scheme_code.toLowerCase().includes(search) &&
        !scheme.amc.toLowerCase().includes(search)
      ) {
        return false;
      }
    }
    return true;
  });

  result = [...result].sort((a, b) => {
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

  return result;
}

export function SchemeTable({ schemes, loading, onSchemeClick }: SchemeTableProps): React.ReactElement {
  const [sortConfig, setSortConfig] = useState<{ key: string; direction: 'asc' | 'desc' }>({ key: 'fund_health_score', direction: 'desc' });
  const [filters, setFilters] = useState({
    category: '',
    minScore: '',
    maxScore: '',
    hasAlerts: false,
    search: '',
  });

  const handleSort = (key: string) => {
    setSortConfig((prev) => ({
      key,
      direction: prev.key === key && prev.direction === 'desc' ? 'asc' : 'desc',
    }));
  };

  const filteredSchemes = useMemo(() => filterAndSortSchemes(schemes, filters, sortConfig), [schemes, filters, sortConfig]);

  const categories = useMemo(() => [...new Set(schemes.map((s) => s.category))].sort(), [schemes]);

  if (loading) {
    return (
      <div className="overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr>
              {['Scheme', 'Category', 'Score', 'Return 1Y', 'Alpha', 'DD', 'Vol', 'Alerts', 'Benchmark'].map((col) => (
                <th key={col} className="px-4 py-3 text-left">
                  <div className="h-4 bg-neutral-200 animate-pulse rounded w-3/4" />
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {[...Array(5)].map((_, i) => (
              <tr key={i}>
                {[...Array(9)].map(() => (
                  <td key={Math.random()} className="px-4 py-3">
                    <div className="h-4 bg-neutral-200 animate-pulse rounded w-3/4" />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="flex flex-wrap gap-4 p-4 bg-white rounded-xl border border-neutral-200">
        <div className="flex-1 min-w-[200px]">
          <label className="block text-sm font-medium text-neutral-700 mb-1">Search</label>
          <input
            type="text"
            placeholder="Search scheme name, code, AMC..."
            value={filters.search}
            onChange={(e) => setFilters({ ...filters, search: e.target.value })}
            className="w-full px-3 py-2 rounded-lg border border-neutral-300 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            placeholder="Search schemes..."
          />
        </div>
        <div className="min-w-[150px]">
          <label className="block text-sm font-medium text-neutral-700 mb-1">Category</label>
          <select
            value={filters.category}
            onChange={(e) => setFilters({ ...filters, category: e.target.value })}
            className="w-full px-3 py-2 rounded-lg border border-neutral-300 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
          >
            <option value="">All Categories</option>
            {categories.map((cat) => (
              <option key={cat} value={cat}>{cat}</option>
            ))}
          </select>
        </div>
        <div className="min-w-[120px]">
          <label className="block text-sm font-medium text-neutral-700 mb-1">Min Score</label>
          <input
            type="number"
            min="0"
            max="100"
            value={filters.minScore}
            onChange={(e) => setFilters({ ...filters, minScore: e.target.value })}
            className="w-full px-3 py-2 rounded-lg border border-neutral-300 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            placeholder="Min"
          />
        </div>
        <div className="min-w-[120px]">
          <label className="block text-sm font-medium text-neutral-700 mb-1">Max Score</label>
          <input
            type="number"
            min="0"
            max="100"
            value={filters.maxScore}
            onChange={(e) => setFilters({ ...filters, maxScore: e.target.value })}
            className="w-full px-3 py-2 rounded-lg border border-neutral-300 focus:ring-2 focus:ring-primary-500 focus:border-transparent"
            placeholder="Max"
          />
        </div>
        <label className="flex items-center gap-2 cursor-pointer self-end">
          <input
            type="checkbox"
            checked={filters.hasAlerts}
            onChange={(e) => setFilters({ ...filters, hasAlerts: e.target.checked })}
            className="w-4 h-4 rounded border-neutral-300 text-primary-600 focus:ring-primary-500"
          />
          <span className="text-sm text-neutral-700">Only with alerts</span>
        </label>
        <button
          onClick={() => setFilters({ category: '', minScore: '', maxScore: '', hasAlerts: false, search: '' })}
          className="self-end px-4 py-2 text-sm text-neutral-600 hover:text-neutral-900"
        >
          Clear filters
        </button>
      </div>

      {/* Table */}
      <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-neutral-50 border-b border-neutral-100 sticky top-0 z-10">
              <tr>
                {[
                  { key: 'scheme_name', label: 'Scheme', width: '250px' },
                  { key: 'category', label: 'Category', width: '140px' },
                  { key: 'amc', label: 'AMC', width: '140px' },
                  { key: 'fund_health_score', label: 'Score', width: '80px', align: 'center' },
                  { key: 'return_1y', label: 'Return 1Y', width: '100px', align: 'right' },
                  { key: 'alpha_1y', label: 'Alpha 1Y', width: '100px', align: 'right' },
                  { key: 'max_drawdown_1y', label: 'Max DD 1Y', width: '100px', align: 'right' },
                  { key: 'volatility_1y', label: 'Vol 1Y', width: '100px', align: 'right' },
                  { key: 'alerts', label: 'Alerts', width: '120px', align: 'center' },
                  { key: 'benchmark', label: 'Benchmark', width: '160px' },
                ].map((col) => (
                  <th
                    key={col.key}
                    className={cn(
                      'px-4 py-3 font-semibold text-neutral-600 uppercase tracking-wider text-xs',
                      col.align === 'center' && 'text-center',
                      col.align === 'right' && 'text-right'
                    )}
                    style={{ width: col.width, minWidth: col.width }}
                  >
                    <button
                      onClick={() =>
                        setSortConfig((prev) => ({
                          key: col.key,
                          direction: prev.key === col.key && prev.direction === 'desc' ? 'asc' : 'desc',
                        }))
                      }
                      className="flex items-center gap-1 hover:text-primary-600"
                    >
                      {col.label}
                      {sortConfig.key === col.key && (
                        sortConfig.direction === 'desc' ? (
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                          </svg>
                        ) : (
                          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        ))
                      }
                    </button>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {filteredSchemes.length === 0 ? (
                <tr>
                  <td colSpan={10} className="px-4 py-12 text-center text-neutral-500">
                    No schemes match the current filters
                  </td>
                </tr>
              ) : (
                filteredSchemes.map((scheme) => {
                  return (
                    <tr
                      key={scheme.scheme_code}
                      className="hover:bg-neutral-50 transition-colors cursor-pointer"
                      onClick={() => onSchemeClick?.(scheme)}
                    >
                      <td className="px-4 py-3">
                        <div className="font-medium text-neutral-900">{truncate(scheme.scheme_name, 30)}</div>
                        <div className="text-xs text-neutral-500">{scheme.scheme_code}</div>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="info" size="sm">{scheme.category}</Badge>
                      </td>
                      <td className="px-4 py-3 text-sm text-neutral-600 truncate max-w-[130px]">{scheme.amc}</td>
                      <td className="text-center">
                        <div className={cn(
                          'inline-flex items-center justify-center px-3 py-1 rounded-full font-semibold text-sm',
                          getScoreColor(scheme.fund_health_score)
                        )}>
                          {scheme.fund_health_score}
                        </div>
                      </td>
                      <td className="text-right font-mono text-sm">
                        {scheme.return_1y !== undefined ? formatPercent(scheme.return_1y) : '—'}
                      </td>
                      <td className="text-right font-mono text-sm">
                        {scheme.alpha_1y !== undefined ? formatPercent(scheme.alpha_1y) : '—'}
                      </td>
                      <td className="text-right font-mono text-sm">
                        {scheme.max_drawdown_1y !== undefined ? formatPercent(scheme.max_drawdown_1y) : '—'}
                      </td>
                      <td className="text-right font-mono text-sm">
                        {scheme.volatility_1y !== undefined ? formatPercent(scheme.volatility_1y) : '—'}
                      </td>
                      <td className="text-center">
                        <div className="flex items-center justify-center gap-1">
                          {scheme.high_alerts > 0 && (
                            <Badge variant="danger" size="sm" dot>{scheme.high_alerts}</Badge>
                          )}
                          {scheme.medium_alerts > 0 && (
                            <Badge variant="warning" size="sm" dot>{scheme.medium_alerts}</Badge>
                          )}
                          {scheme.low_alerts > 0 && (
                            <Badge variant="info" size="sm" dot>{scheme.low_alerts}</Badge>
                          )}
                          {scheme.high_alerts === 0 && scheme.medium_alerts === 0 && scheme.low_alerts === 0 && (
                            <Badge variant="success" size="sm">Clean</Badge>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="text-sm text-neutral-600 truncate max-w-[150px]">{scheme.benchmark_name}</div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}