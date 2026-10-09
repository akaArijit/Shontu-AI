'use client';

import { DashboardLayout } from '@/components/layout/DashboardLayout';
import { AlertsPanel } from '@/components/dashboard/AlertsPanel';
import { useAlerts, useAlertsSummary } from '@/hooks/useQueries';
import { Alert, AlertSummary } from '@/types';

export default function AlertsPage() {
  const { data: alertsData, isLoading } = useAlerts({ unresolved_only: true });
  const { data: summaries } = useAlertsSummary();

  const alerts = alertsData?.alerts || [];
  const summaries = summaries || [];

  if (isLoading) {
    return (
      <DashboardLayout>
        <div className="h-96 bg-white rounded-xl border border-neutral-200 animate-pulse" />
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-neutral-900">Alerts Center</h1>
            <p className="text-neutral-500 mt-1">Manage and resolve fund monitoring alerts</p>
          </div>
        </div>

        <div className="bg-white rounded-xl border border-neutral-200">
          <AlertsPanel
            alerts={alerts}
            summaries={summaries as any}
          />
        </div>
      </div>
    </DashboardLayout>
  );
}