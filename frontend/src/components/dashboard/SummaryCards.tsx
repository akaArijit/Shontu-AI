'use client';

import { cn } from '@/lib/utils';
import { 
  TrendingUp, 
  TrendingDown, 
  AlertTriangle, 
  BarChart2,
  Target,
  Users
} from 'lucide-react';
import { Card } from '@/components/ui/Card';
import { formatNumber } from '@/lib/utils';

interface SummaryCardProps {
  title: string;
  value: string | number;
  change?: number;
  changeLabel?: string;
  icon: React.ReactNode;
  iconColor: string;
  trend?: 'up' | 'down' | 'neutral';
}

export function SummaryCard({ title, value, change, changeLabel, icon, iconColor, trend }: SummaryCardProps) {
  return (
    <Card className="h-full">
      <div className="flex items-start justify-between">
        <div>
          <p className="text-sm font-medium text-neutral-500">{title}</p>
          <p className="text-2xl font-bold text-neutral-900 mt-1">{value}</p>
          {change !== undefined && (
            <p className={cn(
              'text-sm mt-1 flex items-center gap-1',
              trend === 'up' ? 'text-success-600' : trend === 'down' ? 'text-danger-600' : 'text-neutral-500'
            )}>
              {trend === 'up' && <TrendingUp className="w-3.5 h-3.5" />}
              {trend === 'down' && <TrendingDown className="w-3.5 h-3.5" />}
              <span>{change >= 0 ? '+' : ''}{change}%</span>
              {changeLabel && <span className="text-neutral-500">{changeLabel}</span>}
            </p>
          )}
        </div>
        <div className={cn('p-2 rounded-lg', iconColor)}>
          {icon}
        </div>
      </div>
    </Card>
  );
}

export function DashboardSummary({ 
  totalSchemes, 
  avgScore, 
  highAlerts, 
  mediumAlerts, 
  lowAlerts,
  schemesWithAlerts,
  totalFolios,
  totalAUM
}: {
  totalSchemes: number;
  avgScore: number;
  highAlerts: number;
  mediumAlerts: number;
  lowAlerts: number;
  schemesWithAlerts: number;
  totalFolios: number;
  totalAUM: number;
}) {
  return (
    <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
      <SummaryCard
        title="Total Schemes"
        value={totalSchemes}
        change={2.3}
        changeLabel="vs last month"
        icon={<BarChart2 className="w-6 h-6" />}
        iconColor="bg-primary-100 text-primary-600"
        trend="up"
      />
      <SummaryCard
        title="Avg Fund Score"
        value={avgScore.toFixed(1)}
        change={1.2}
        changeLabel="vs last quarter"
        icon={<Target className="w-6 h-6" />}
        iconColor="bg-success-100 text-success-600"
        trend="up"
      />
      <SummaryCard
        title="Total AUM"
        value={`${formatNumber(totalAUM / 1e7)} Cr`}
        change={5.4}
        changeLabel="vs last year"
        icon={<Users className="w-6 h-6" />}
        iconColor="bg-warning-100 text-warning-600"
        trend="up"
      />
      <SummaryCard
        title="Total Folios"
        value={totalFolios.toLocaleString()}
        change={-0.8}
        changeLabel="vs last month"
        icon={<Users className="w-6 h-6" />}
        iconColor="bg-primary-100 text-primary-600"
        trend="down"
      />
      
      {/* Alert Summary */}
      <div className="col-span-1 sm:col-span-2 lg:col-span-4">
        <Card>
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-lg font-semibold text-neutral-900">Alert Summary</h3>
            <span className="text-sm text-neutral-500">
              {highAlerts + mediumAlerts + lowAlerts} total • {schemesWithAlerts} schemes affected
            </span>
          </div>
          <div className="grid grid-cols-3 gap-4">
            <div className="p-4 rounded-lg bg-danger-50 border border-danger-100">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-2 h-2 rounded-full bg-danger-500" />
                <span className="text-sm font-medium text-danger-700">High</span>
              </div>
              <p className="text-3xl font-bold text-danger-600">{highAlerts}</p>
              <p className="text-xs text-danger-500">Immediate action required</p>
            </div>
            <div className="p-4 rounded-lg bg-warning-50 border border-warning-100">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-2 h-2 rounded-full bg-warning-500" />
                <span className="text-sm font-medium text-warning-700">Medium</span>
              </div>
              <p className="text-3xl font-bold text-warning-600">{mediumAlerts}</p>
              <p className="text-xs text-warning-500">Review this week</p>
            </div>
            <div className="p-4 rounded-lg bg-primary-50 border border-primary-100">
              <div className="flex items-center gap-2 mb-2">
                <div className="w-2 h-2 rounded-full bg-primary-500" />
                <span className="text-sm font-medium text-primary-700">Low</span>
              </div>
              <p className="text-3xl font-bold text-primary-600">{lowAlerts}</p>
              <p className="text-xs text-primary-500">Monitor</p>
            </div>
          </div>
        </Card>
      </div>
    </div>
  );
}