'use client';

import React from 'react';
import { useState } from 'react';
import { cn, getSeverityColor, getAlertTypeLabel, formatDate } from '@/lib/utils';
import { Alert, AlertSummary } from '@/types';
import { Card } from '@/components/ui/Card';
import { Badge } from '@/components/ui/Badge';
import { Button } from '@/components/ui/Button';
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/Table';
import { Checkbox } from '@/components/ui/Checkbox';
import { MoreHorizontal, ChevronDown, ChevronUp, AlertTriangle, X, Check } from 'lucide-react';

interface AlertsPanelProps {
  alerts: Alert[];
  summaries: AlertSummary[];
  onResolve?: (alertId: string) => void;
  onDismiss?: (alertId: string, reason: string) => void;
}

export function AlertsPanel({ alerts, summaries, onResolve, onDismiss }: AlertsPanelProps): React.ReactElement {
  const [selectedAlerts, setSelectedAlerts] = useState<Set<string>>(new Set());
  const [showDismissModal, setShowDismissModal] = useState<string | null>(null);
  const [dismissReason, setDismissReason] = useState('');

  const handleSelectAll = (checked: boolean) => {
    if (checked) {
      setSelectedAlerts(new Set(alerts.map((a) => a.alert_id)));
    } else {
      setSelectedAlerts(new Set());
    }
  };

  const handleSelectOne = (alertId: string, checked: boolean) => {
    setSelectedAlerts((prev) => {
      const next = new Set(prev);
      if (checked) next.add(alertId);
      else next.delete(alertId);
      return next;
    });
  };

  const handleBulkResolve = async () => {
    const ids = Array.from(selectedAlerts);
    if (ids.length === 0) return;
    if (onResolve) {
      ids.forEach((id) => onResolve(id));
    }
    setSelectedAlerts(new Set());
  };

  const handleBulkDismiss = async () => {
    const ids = Array.from(selectedAlerts);
    if (ids.length === 0 || !dismissReason.trim()) return;
    if (onDismiss) {
      ids.forEach((id) => onDismiss(id, dismissReason));
    }
    setSelectedAlerts(new Set());
    setShowDismissModal(null);
    setDismissReason('');
  };

  const handleResolve = async (alertId: string) => {
    if (onResolve) onResolve(alertId);
  };

  const handleDismiss = (alertId: string) => {
    setShowDismissModal(alertId);
    setDismissReason('');
  };

  const handleConfirmDismiss = async (alertId: string) => {
    if (!dismissReason.trim()) return;
    if (onDismiss) onDismiss(alertId, dismissReason);
    setShowDismissModal(null);
    setDismissReason('');
  };

  const totalHigh = summaries.find((s) => s.severity === 'high')?.count || 0;
  const totalMedium = summaries.find((s) => s.severity === 'medium')?.count || 0;
  const totalLow = summaries.find((s) => s.severity === 'low')?.count || 0;

  return (
    <div className="space-y-4">
      {/* Summary Bar */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-4">
          <div className={cn('flex items-center gap-2 px-3 py-1.5 rounded-full', getSeverityColor('danger'))}>
            <span className="w-2 h-2 rounded-full bg-danger-500" />
            <span className="text-sm font-medium text-danger-700">{totalHigh} High</span>
          </div>
          <div className={cn('flex items-center gap-2 px-3 py-1.5 rounded-full', getSeverityColor('warning'))}>
            <span className="w-2 h-2 rounded-full bg-warning-500" />
            <span className="text-sm font-medium text-warning-700">{totalMedium} Medium</span>
          </div>
          <div className={cn('flex items-center gap-2 px-3 py-1.5 rounded-full', getSeverityColor('low'))}>
            <span className="w-2 h-2 rounded-full bg-primary-500" />
            <span className="text-sm font-medium text-primary-700">{totalLow} Low</span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {selectedAlerts.size > 0 && (
            <>
              <Button variant="primary" size="sm" onClick={handleBulkResolve}>
                <Check className="w-4 h-4 mr-1" />
                Resolve ({selectedAlerts.size})
              </Button>
              <Button variant="outline" size="sm" onClick={() => setShowDismissModal('bulk')}>
                <X className="w-4 h-4 mr-1" />
                Dismiss ({selectedAlerts.size})
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Dismiss Modal */}
      {showDismissModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/50">
          <div className="bg-white rounded-xl p-6 max-w-md w-full">
            <h3 className="text-lg font-semibold text-neutral-900 mb-2">
              {showDismissModal === 'bulk' ? `Dismiss ${selectedAlerts.size} alerts` : 'Dismiss alert'}
            </h3>
            <p className="text-neutral-600 mb-4">
              {showDismissModal === 'bulk'
                ? 'This will dismiss all selected alerts. Please provide a reason.'
                : 'This will dismiss the selected alert. Please provide a reason.'}
            </p>
            <textarea
              value={dismissReason}
              onChange={(e) => setDismissReason(e.target.value)}
              placeholder="Reason for dismissal (e.g., 'False positive', 'Client informed', 'Data error')"
              className="w-full px-3 py-2 rounded-lg border border-neutral-300 focus:ring-2 focus:ring-primary-500 focus:border-transparent min-h-[80px] resize-y mb-4"
              rows={3}
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowDismissModal(null);
                  setDismissReason('');
                }}
                className="px-4 py-2 text-neutral-600 hover:text-neutral-900"
              >
                Cancel
              </button>
              <Button
                onClick={() => (showDismissModal === 'bulk' ? handleBulkDismiss() : handleConfirmDismiss(showDismissModal))}
                disabled={!dismissReason.trim()}
              >
                Dismiss
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Alerts Table */}
      <div className="bg-white rounded-xl border border-neutral-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead className="bg-neutral-50 border-b border-neutral-100 sticky top-0 z-10">
              <tr>
                <th className="px-4 py-3 w-12"></th>
                <th className="px-4 py-3 font-semibold text-neutral-600 uppercase tracking-wider text-xs">Severity</th>
                <th className="px-4 py-3 font-semibold text-neutral-600 uppercase tracking-wider text-xs">Alert Type</th>
                <th className="px-4 py-3 font-semibold text-neutral-600 uppercase tracking-wider text-xs">Scheme</th>
                <th className="px-4 py-3 font-semibold text-neutral-600 uppercase tracking-wider text-xs">Category</th>
                <th className="px-4 py-3 font-semibold text-neutral-600 uppercase tracking-wider text-xs">Triggered</th>
                <th className="px-4 py-3 font-semibold text-neutral-600 uppercase tracking-wider text-xs w-48">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-neutral-100">
              {alerts.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-neutral-500">
                    <div className="flex flex-col items-center gap-2">
                      <AlertTriangle className="w-12 h-12 text-neutral-300" />
                      <p className="text-neutral-500">No unresolved alerts</p>
                    </div>
                  </td>
                </tr>
              ) : (
                alerts.map((alert) => {
                  return (
                    <tr key={alert.alert_id} className="hover:bg-neutral-50">
                      <td className="px-4 py-3">
                        <input
                          type="checkbox"
                          checked={selectedAlerts.has(alert.alert_id)}
                          onChange={(e) => handleSelectOne(alert.alert_id, e.target.checked)}
                          className="w-4 h-4 rounded border-neutral-300 text-primary-600 focus:ring-primary-500"
                        />
                      </td>
                      <td className="px-4 py-3">
                        <Badge
                          variant={alert.severity === 'high' ? 'danger' : alert.severity === 'medium' ? 'warning' : 'info'}
                          size="sm"
                          dot
                        >
                          {alert.severity.toUpperCase()}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <Badge variant="neutral" size="sm">
                          {getAlertTypeLabel(alert.alert_type)}
                        </Badge>
                      </td>
                      <td className="px-4 py-3">
                        <div className="font-medium text-neutral-900">{alert.scheme_name}</div>
                        <div className="text-xs text-neutral-500">{alert.scheme_code}</div>
                      </td>
                      <td className="px-4 py-3 text-sm text-neutral-600">{alert.category}</td>
                      <td className="px-4 py-3 text-sm text-neutral-600">{formatDate(alert.triggered_on)}</td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1 justify-end">
                          <button
                            onClick={() => handleResolve(alert.alert_id)}
                            className="p-1.5 rounded hover:bg-success-50 text-success-600"
                            title="Resolve"
                          >
                            <Check className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDismiss(alert.alert_id)}
                            className="p-1.5 rounded hover:bg-neutral-100 text-neutral-600"
                            title="Dismiss"
                          >
                            <X className="w-4 h-4" />
                          </button>
                        </div>
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