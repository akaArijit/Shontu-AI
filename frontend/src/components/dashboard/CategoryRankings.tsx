'use client';

import React from 'react';
import { useState } from 'react';
import { cn, formatPercent, formatNumber, formatRank, getScoreColor } from '@/lib/utils';
import { CategoryRankingItem } from '@/types';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { Badge } from '@/components/ui/Badge';
import { Select } from '@/components/ui/Select';
import { ChevronDown, ChevronUp } from 'lucide-react';

interface CategoryRankingsProps {
  rankings: CategoryRankingItem[];
  category: string;
}

export function CategoryRankings({ rankings, category }: CategoryRankingsProps) {
  const [sortConfig, setSortConfig] = useState<{ key: string; direction: 'asc' | 'desc' }>({ key: 'fund_health_score', direction: 'desc' });
  const [metric, setMetric] = useState<'score' | 'return' | 'alpha' | 'dd' | 'vol'>('score');

  const sortedRankings = [...rankings].sort((a, b) => {
    const getValue = (item: CategoryRankingItem) => {
      switch (sortConfig.key) {
        case 'fund_health_score': return item.fund_health_score;
        case 'return_1y': return item.return_1y ?? -999;
        case 'alpha_1y': return item.alpha_1y ?? -999;
        case 'max_drawdown_1y': return item.max_drawdown_1y ?? 999;
        case 'volatility_1y': return item.volatility_1y ?? 999;
        case 'category_rank': return item.category_rank ?? 999;
        default: return item.fund_health_score;
      }
    };
    const aVal = getValue(a);
    const bVal = getValue(b);
    if (aVal === bVal) return 0;
    return sortConfig.direction === 'asc' ? aVal - bVal : bVal - aVal;
  });

  const handleSort = (key: string) => {
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'desc' ? 'asc' : 'desc',
    }));
  };

  const metricLabels: Record<string, string> = {
    score: 'Score',
    return: 'Return 1Y',
    alpha: 'Alpha 1Y',
    dd: 'Max DD 1Y',
    vol: 'Vol 1Y',
  };

  return (
    <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
      <div className="px-6 py-4 border-b border-neutral-100 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-lg font-semibold text-neutral-900">{category}</h3>
          <Badge variant="info" size="sm">{rankings.length} schemes</Badge>
        </div>
        <div className="flex items-center gap-4">
          <Select
            value={metric}
            onChange={e => setMetric(e.target.value as any)}
            options={[
              { value: 'score', label: 'Score' },
              { value: 'return', label: 'Return 1Y' },
              { value: 'alpha', label: 'Alpha 1Y' },
              { value: 'dd', label: 'Max DD 1Y' },
              { value: 'vol', label: 'Vol 1Y' },
            ]}
            className="w-[140px]"
          />
        </div>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full">
          <thead className="bg-neutral-50 border-b border-neutral-100 sticky top-0 z-10">
            <tr>
              {[
                { key: 'category_rank', label: 'Rank', width: '70px' },
                { key: 'scheme_name', label: 'Scheme', width: '250px' },
                { key: 'amc', label: 'AMC', width: '140px' },
                { key: 'fund_health_score', label: 'Score', width: '80px' },
                { key: 'return_1y', label: 'Return 1Y', width: '100px' },
                { key: 'alpha_1y', label: 'Alpha 1Y', width: '100px' },
                { key: 'max_drawdown_1y', label: 'Max DD 1Y', width: '100px' },
                { key: 'volatility_1y', label: 'Vol 1Y', width: '100px' },
                { key: 'category_percentile', label: 'Percentile', width: '100px' },
              ].map(col => (
                <th
                  key={col.key}
                  className={cn(
                    'px-4 py-3 font-semibold text-neutral-600 uppercase tracking-wider text-xs',
                    col.key !== 'scheme_name' && 'text-center'
                  )}
                  style={{ width: col.width, minWidth: col.width }}
                >
                  <button
                    onClick={() => handleSort(col.key)}
                    className="flex items-center gap-1 hover:text-primary-600 justify-center"
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
            {sortedRankings.map((item, index) => (
              <tr key={item.scheme_code} className="hover:bg-neutral-50">
                <td className="px-4 py-3 text-center font-medium text-neutral-600">
                  {item.category_rank || index + 1}
                </td>
                <td className="px-4 py-3">
                  <div className="font-medium text-neutral-900">{item.scheme_name}</div>
                  <div className="text-xs text-neutral-500">{item.scheme_code}</div>
                </td>
                <td className="px-4 py-3 text-center text-sm text-neutral-600">{item.amc}</td>
                <td className="text-center">
                  <div className={cn(
                    'inline-flex items-center justify-center px-3 py-1 rounded-full font-semibold text-sm',
                    getScoreColor(item.fund_health_score)
                  )}>
                    {item.fund_health_score}
                  </div>
                </td>
                <td className="text-right font-mono text-sm">
                  {item.return_1y !== undefined ? formatPercent(item.return_1y) : '—'}
                </td>
                <td className="text-right font-mono text-sm">
                  {item.alpha_1y !== undefined ? formatPercent(item.alpha_1y) : '—'}
                </td>
                <td className="text-right font-mono text-sm">
                  {item.max_drawdown_1y !== undefined ? formatPercent(item.max_drawdown_1y) : '—'}
                </td>
                <td className="text-right font-mono text-sm">
                  {item.volatility_1y !== undefined ? formatPercent(item.volatility_1y) : '—'}
                </td>
                <td className="text-center">
                  <Badge variant="info" size="sm">
                    {item.category_percentile !== undefined ? formatNumber(item.category_percentile) + 'th' : '—'}
                  </Badge>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}