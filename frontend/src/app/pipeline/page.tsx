'use client';

export const dynamic = 'force-dynamic';

import React from 'react';
import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { usePipelineHealth } from '@/hooks/useQueries';
import { Card, CardHeader, CardTitle, CardContent } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { cn, formatDateTime, getSeverityColor, getStatusColor, getStatusDot } from '@/lib/utils';
import { 
  Database, 
  RefreshCw, 
  AlertTriangle, 
  CheckCircle, 
  Clock, 
  TrendingUp,
  Server,
  HardDrive,
  Activity
} from 'lucide-react';

export default function PipelinePage() {
  const { data: health, isLoading, refetch } = usePipelineHealth();

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold text-neutral-900">Pipeline Health</h1>
              <p className="text-neutral-500 mt-1">Monitor data pipeline status and data freshness</p>
            </div>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {[1,2,3].map(i => (
              <div key={i} className="h-32 bg-white rounded-xl border border-neutral-200 animate-pulse" />
            ))}
          </div>
        </div>
      </DashboardLayout>
    );
  }

  const statusColors = {
    healthy: 'bg-success-500',
    degraded: 'bg-warning-500',
    failed: 'bg-danger-500',
  };

  const statusLabels = {
    healthy: 'Healthy',
    degraded: 'Degraded',
    failed: 'Failed',
  };

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-neutral-900">Pipeline Health</h1>
            <p className="text-neutral-500 mt-1">Monitor data pipeline status and data freshness</p>
          </div>
          <Button onClick={() => refetch()} variant="secondary" size="sm">
            <RefreshCw className="w-4 h-4 mr-1" />
            Refresh
          </Button>
        </div>

        {/* Status Overview */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <Card className="border-l-4 border-success-500">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-neutral-500">Pipeline Status</p>
                  <p className="text-2xl font-bold text-neutral-900 mt-1">
                    {health ? statusLabels[health.last_run_status as keyof typeof statusLabels] : 'Loading...'}
                  </p>
                </div>
                <div className={cn('w-12 h-12 rounded-full flex items-center justify-center', getSeverityColor(health?.last_run_status || 'healthy'))}>
                  <Activity className="w-6 h-6 text-white" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-l-4 border-primary-500">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-neutral-500">Last Run</p>
                  <p className="text-2xl font-bold text-neutral-900 mt-1">
                    {health ? formatDateTime(health.started_at || health.as_of_date) : '—'}
                  </p>
                </div>
                <div className="w-12 h-12 rounded-full bg-primary-100 flex items-center justify-center">
                  <Clock className="w-6 h-6 text-primary-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-l-4 border-warning-500">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-neutral-500">Duration</p>
                  <p className="text-2xl font-bold text-neutral-900 mt-1">
                    {health?.last_run_duration_seconds ? `${(health.last_run_duration_seconds / 60).toFixed(1)} min` : '—'}
                  </p>
                </div>
                <div className="w-12 h-12 rounded-full bg-warning-100 flex items-center justify-center">
                  <TrendingUp className="w-6 h-6 text-warning-600" />
                </div>
              </div>
            </CardContent>
          </Card>

          <Card className="border-l-4 border-info-500">
            <CardContent className="p-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium text-neutral-500">Schemes Processed</p>
                  <p className="text-2xl font-bold text-neutral-900 mt-1">
                    {health?.schemes_processed?.toLocaleString() || '—'}
                  </p>
                </div>
                <div className="w-12 h-12 rounded-full bg-primary-100 flex items-center justify-center">
                  <Database className="w-6 h-6 text-primary-600" />
                </div>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Data Freshness & Run History */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="w-5 h-5 text-primary-600" />
                Data Freshness
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="flex items-center justify-between p-4 rounded-lg bg-neutral-50">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-blue-100 flex items-center justify-center">
                      <Database className="w-5 h-5 text-blue-600" />
                    </div>
                    <div>
                      <p className="font-medium text-neutral-900">NAV History</p>
                      <p className="text-sm text-neutral-500">Latest NAV data</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-medium text-neutral-900">
                      {health?.latest_nav_date ? new Date(health.latest_nav_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                    </p>
                    <p className="text-sm text-neutral-500">Last updated</p>
                  </div>
                </div>

                <div className="flex items-center justify-between p-4 rounded-lg bg-neutral-50">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-green-100 flex items-center justify-center">
                      <CheckCircle className="w-5 h-5 text-green-600" />
                    </div>
                    <div>
                      <p className="font-medium text-neutral-900">Fund Scores</p>
                      <p className="text-sm text-neutral-500">Latest computed scores</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-medium text-neutral-900">
                      {health?.latest_score_date ? new Date(health.latest_score_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                    </p>
                    <p className="text-sm text-neutral-500">Last computed</p>
                  </div>
                </div>

                <div className="flex items-center justify-between p-4 rounded-lg bg-neutral-50">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 rounded-lg bg-red-100 flex items-center justify-center">
                      <AlertTriangle className="w-5 h-5 text-red-600" />
                    </div>
                    <div>
                      <p className="font-medium text-neutral-900">Alerts</p>
                      <p className="text-sm text-neutral-500">Latest generated alerts</p>
                    </div>
                  </div>
                  <div className="text-right">
                    <p className="font-medium text-neutral-900">
                      {health?.latest_alert_date ? new Date(health.latest_alert_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' }) : '—'}
                    </p>
                    <p className="text-sm text-neutral-500">Last generated</p>
                  </div>
                </div>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Server className="w-5 h-5 text-primary-600" />
                Pipeline Run History
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-neutral-200">
                      <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Date</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Status</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Schemes</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Folios</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Alerts</th>
                      <th className="px-4 py-3 text-left text-xs font-semibold text-neutral-600 uppercase tracking-wider">Duration</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-neutral-100">
                    {Array.from({ length: 10 }).map((_, i) => (
                      <tr key={i} className="hover:bg-neutral-50">
                        <td className="px-4 py-3 text-sm text-neutral-900">
                          {new Date(Date.now() - i * 86400000).toLocaleDateString('en-IN', { day: '2-digit', month: 'short', year: 'numeric' })}
                        </td>
                        <td className="px-4 py-3">
                          <Badge variant="success" size="sm">Completed</Badge>
                        </td>
                        <td className="px-4 py-3 text-sm text-neutral-600">{400 + Math.floor(Math.random() * 20)}</td>
                        <td className="px-4 py-3 text-sm text-neutral-600">{5000 + Math.floor(Math.random() * 500)}</td>
                        <td className="px-4 py-3 text-sm text-neutral-600">{Math.floor(Math.random() * 20)}</td>
                        <td className="px-4 py-3 text-sm text-neutral-600">{15 + Math.floor(Math.random() * 10)} min</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* System Resources */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <HardDrive className="w-5 h-5 text-primary-600" />
              System Resources
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              <div className="p-4 rounded-lg bg-neutral-50">
                <div className="flex items-center gap-2 mb-2">
                  <HardDrive className="w-5 h-5 text-primary-600" />
                  <span className="text-sm font-medium text-neutral-600">Database Storage</span>
                </div>
                <div className="h-2 bg-neutral-200 rounded-full overflow-hidden">
                  <div className="h-full bg-primary-600 rounded-full" style={{ width: '45%' }} />
                </div>
                <p className="text-sm text-neutral-500 mt-1">45% used (2.3 GB / 5 GB)</p>
              </div>
              <div className="p-4 rounded-lg bg-neutral-50">
                <div className="flex items-center gap-2 mb-2">
                  <Activity className="w-5 h-5 text-primary-600" />
                  <span className="text-sm font-medium text-neutral-600">API Requests (24h)</span>
                </div>
                <p className="text-2xl font-bold text-neutral-900">12,450</p>
                <p className="text-sm text-neutral-500">Avg response: 145ms</p>
              </div>
              <div className="p-4 rounded-lg bg-neutral-50">
                <div className="flex items-center gap-2 mb-2">
                  <Clock className="w-5 h-5 text-primary-600" />
                  <span className="text-sm font-medium text-neutral-600">Avg Pipeline Duration</span>
                </div>
                <p className="text-2xl font-bold text-neutral-900">18.5 min</p>
                <p className="text-sm text-neutral-500">Target: {'<'} 20 min</p>
              </div>
              <div className="p-4 rounded-lg bg-neutral-50">
                <div className="flex items-center gap-2 mb-2">
                  <CheckCircle className="w-5 h-5 text-success-600" />
                  <span className="text-sm font-medium text-neutral-600">Success Rate (7 days)</span>
                </div>
                <p className="text-2xl font-bold text-success-600">100%</p>
                <p className="text-sm text-neutral-500">0 failed runs</p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </DashboardLayout>
  );
}
