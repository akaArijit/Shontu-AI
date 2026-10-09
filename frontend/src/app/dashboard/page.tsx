'use client';

import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { DashboardSummary } from '@/components/dashboard/SummaryCards';
import { SchemeTable } from '@/components/dashboard/SchemeTable';
import { AlertsPanel } from '@/components/dashboard/AlertsPanel';
import { CategoryRankings } from '@/components/dashboard/CategoryRankings';
import { useSchemes, useScores, useAlerts, useAlertsSummary, useAllCategoryRankings, usePipelineHealth } from '@/hooks/useQueries';
import { MFDSchemeSummary, Alert, AlertSummary } from '@/types';

export default function DashboardPage() {
  const { data: schemesData, isLoading: schemesLoading } = useSchemes({});
  const { data: scoresData } = useScores({});
  const { data: alertsData, isLoading: alertsLoading } = useAlerts({ unresolved_only: true });
  const { data: alertsSummary } = useAlertsSummary();
  const { data: categoryRankings } = useAllCategoryRankings();
  const { data: health, isLoading: healthLoading } = usePipelineHealth();

  const schemes = schemesData?.schemes || [];
  const scores = scoresData?.scores || [];
  const alerts = alertsData?.alerts || [];
  const summaries = alertsSummary || [];
  const rankings = categoryRankings || [];

  // Merge scores into schemes for display
  const scoreMap = new Map(scores.map(s => [s.scheme_code, s]));
  const schemesWithScores: typeof schemes = schemes.map(scheme => {
    const score = scoreMap.get(scheme.scheme_code);
    return {
      ...scheme,
      fund_health_score: score?.fund_health_score,
      category_rank: score?.category_rank,
      category_percentile: score?.category_percentile,
      alpha_1y: score?.breakdown?.find(b => b.component === 'benchmark_outperformance')?.raw_value,
      return_1y: score?.rolling_returns?.return_1y,
      max_drawdown_1y: score?.breakdown?.find(b => b.component === 'drawdown_control')?.raw_value,
      volatility_1y: score?.breakdown?.find(b => b.component === 'volatility_adjusted')?.raw_value,
    };
  });

  if (schemesLoading || healthLoading) {
    return (
      <DashboardLayout>
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {[1,2,3,4].map(i => (
              <div key={i} className="h-24 bg-white rounded-xl border border-neutral-200 animate-pulse" />
            ))}
          </div>
          <div className="h-96 bg-white rounded-xl border border-neutral-200 animate-pulse" />
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-neutral-900">Fund Monitoring Dashboard</h1>
            <p className="text-neutral-500 mt-1">Monitor fund health scores, alerts, and rankings across all schemes</p>
          </div>
          <div className="flex items-center gap-2 text-sm text-neutral-500">
            <span>Data as of:</span>
            <time className="font-medium text-neutral-900">
              {health?.latest_score_date ? new Date(health.latest_score_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
            </time>
          </div>
        </div>

        {/* Summary Cards */}
        <DashboardSummary
          totalSchemes={schemes.length}
          avgScore={scores.length > 0 ? scores.reduce((a, b) => a + b.fund_health_score, 0) / scores.length : 0}
          highAlerts={alerts.filter(a => a.severity === 'high').length}
          mediumAlerts={alerts.filter(a => a.severity === 'medium').length}
          lowAlerts={alerts.filter(a => a.severity === 'low').length}
          schemesWithAlerts={new Set(alerts.map(a => a.scheme_code)).size}
          totalFolios={0}
          totalAUM={0}
        />

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left: Scheme Table */}
          <div className="lg:col-span-2">
            <div className="bg-white rounded-xl border border-neutral-200">
              <div className="px-6 py-4 border-b border-neutral-100 flex items-center justify-between">
                <h2 className="text-lg font-semibold text-neutral-900">All Schemes</h2>
                <div className="flex items-center gap-2 text-sm text-neutral-500">
                  <span>{schemes.length} schemes</span>
                  <span className="text-neutral-300">|</span>
                  <span>{new Set(schemes.map(s => s.category)).size} categories</span>
                  <span className="text-neutral-300">|</span>
                  <span>{new Set(schemes.map(s => s.amc)).size} AMCs</span>
                </div>
              </div>
              <SchemeTable
                schemes={schemesWithScores as any}
                loading={schemesLoading}
              />
            </div>
          </div>

          {/* Right: Alerts Panel */}
          <div className="lg:col-span-1">
            <div className="bg-white rounded-xl border border-neutral-200 sticky top-24 h-[calc(100vh-120px)] overflow-hidden">
              <AlertsPanel
                alerts={alerts}
                summaries={summaries as any}
              />
            </div>
          </div>
        </div>

        {/* Category Rankings */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 mt-6">
          {categoryRankings.map((catRanking: any) => (
            <CategoryRankings
              key={catRanking.category}
              rankings={catRanking.rankings}
              category={catRanking.category}
            />
          ))}
        </div>
      </div>
    </DashboardLayout>
  );
}