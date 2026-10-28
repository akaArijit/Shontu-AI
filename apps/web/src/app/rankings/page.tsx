'use client';

export const dynamic = 'force-dynamic';

import React from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { CategoryRankings } from '@/components/dashboard/CategoryRankings';
import { useAllCategoryRankings } from '@/hooks/useQueries';

export default function RankingsPage() {
  const { data: categoryRankings, isLoading } = useAllCategoryRankings();

  const rankings = categoryRankings || [];

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-neutral-900">Category Rankings</h1>
              <p className="text-neutral-500 mt-1">Peer comparison within SEBI categories</p>
            </div>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {[1, 2, 3, 4, 5, 6].map(i => (
              <div key={i} className="h-96 bg-white rounded-xl border border-neutral-200 animate-pulse" />
            ))}
          </div>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-neutral-900">Category Rankings</h1>
            <p className="text-neutral-500 mt-1">Peer comparison within SEBI categories</p>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {rankings.map((catRanking: any) => (
            <div key={catRanking.category} className="h-[600px]">
              <div 
                className="bg-white rounded-xl border border-neutral-200 h-full"
                style={{ maxHeight: '600px', overflow: 'auto' }}
              >
                <div className="px-6 py-4 border-b border-neutral-100 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <h3 className="text-lg font-semibold text-neutral-900">{catRanking.category}</h3>
                    <span className="px-2 py-1 text-xs font-medium bg-primary-50 text-primary-700 rounded-full">
                      {catRanking.rankings.length} schemes
                    </span>
                  </div>
                </div>
                <div style={{ maxHeight: '500px', overflow: 'auto' }}>
                  <table className="w-full">
                    <thead className="bg-neutral-50 border-b border-neutral-100 sticky top-0 z-10">
                      <tr>
                        <th className="px-4 py-3 text-left font-semibold text-neutral-600 uppercase tracking-wider text-xs w-16">Rank</th>
                        <th className="px-4 py-3 font-semibold text-neutral-600 uppercase tracking-wider text-xs">Scheme</th>
                        <th className="px-4 py-3 font-semibold text-neutral-600 uppercase tracking-wider text-xs text-center w-32">AMC</th>
                        <th className="px-4 py-3 font-semibold text-neutral-600 uppercase tracking-wider text-xs text-center w-20">Score</th>
                        <th className="px-4 py-3 font-semibold text-neutral-600 uppercase tracking-wider text-xs text-right w-28">Return 1Y</th>
                        <th className="px-4 py-3 font-semibold text-neutral-600 uppercase tracking-wider text-xs text-right w-28">Alpha</th>
                        <th className="px-4 py-3 font-semibold text-neutral-600 uppercase tracking-wider text-xs text-right w-28">Max DD</th>
                        <th className="px-4 py-3 font-semibold text-neutral-600 uppercase tracking-wider text-xs text-right w-28">Vol</th>
                        <th className="px-4 py-3 font-semibold text-neutral-600 uppercase tracking-wider text-xs text-center w-24">Pctl</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-neutral-100">
                      {catRanking.rankings.map((item: any, index: number) => (
                        <tr key={item.scheme_code} className="hover:bg-neutral-50">
                          <td className="px-4 py-3 text-center font-medium text-neutral-600">{item.category_rank || index + 1}</td>
                          <td className="px-4 py-3">
                            <div className="font-medium text-neutral-900">{item.scheme_name}</div>
                            <div className="text-xs text-neutral-500">{item.scheme_code}</div>
                          </td>
                          <td className="px-4 py-3 text-center text-sm text-neutral-600">{item.amc}</td>
                          <td className="text-center">
                            <div className="inline-flex items-center justify-center px-3 py-1 rounded-full font-semibold text-sm bg-green-100 text-green-800">
                              {item.fund_health_score}
                            </div>
                          </td>
                          <td className="text-right font-mono text-sm">
                            {item.return_1y !== undefined ? `${(item.return_1y * 100).toFixed(2)}%` : '—'}
                          </td>
                          <td className="text-right font-mono text-sm">
                            {item.alpha_1y !== undefined ? `${(item.alpha_1y * 100).toFixed(2)}%` : '—'}
                          </td>
                          <td className="text-right font-mono text-sm">
                            {item.max_drawdown_1y !== undefined ? `${(item.max_drawdown_1y * 100).toFixed(1)}%` : '—'}
                          </td>
                          <td className="text-right font-mono text-sm">
                            {item.volatility_1y !== undefined ? `${(item.volatility_1y * 100).toFixed(1)}%` : '—'}
                          </td>
                          <td className="text-center">
                            <span className="px-2 py-1 text-xs font-medium bg-primary-50 text-primary-700 rounded-full">
                              {item.category_percentile !== undefined ? item.category_percentile.toFixed(1) + 'th' : '—'}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </DashboardLayout>
  );
}