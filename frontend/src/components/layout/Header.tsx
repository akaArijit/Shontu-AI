'use client';

import { usePipelineHealth } from '@/hooks/useQueries';
import { cn, formatDateTime, getSeverityColor, getSeverityIcon } from '@/lib/utils';
import { RefreshCw, AlertTriangle, Bell, Menu, ChevronDown, ExternalLink } from 'lucide-react';
import Link from 'next/link';
import { useState } from 'react';

interface HeaderProps {
  onMenuClick?: () => void;
  sidebarCollapsed?: boolean;
}

export function Header({ onMenuClick, sidebarCollapsed }: HeaderProps) {
  const { data: health, isLoading } = usePipelineHealth();
  const [showNotifications, setShowNotifications] = useState(false);

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

  const runStatus = (health?.last_run_status || '').toLowerCase();
  const statusTone: keyof typeof statusColors =
    !runStatus || runStatus === 'healthy' || runStatus === 'success' || runStatus === 'completed'
      ? 'healthy'
      : runStatus === 'degraded' || runStatus === 'partial' || runStatus === 'running'
        ? 'degraded'
        : 'failed';

  return (
    <header
      className={cn(
        'fixed top-0 right-0 h-16 bg-white border-b border-neutral-200 z-40 flex items-center justify-between px-4 lg:px-6',
        sidebarCollapsed ? 'lg:ml-16' : 'lg:ml-64'
      )}
      role="banner"
    >
      {/* Left: Menu toggle */}
      <div className="flex items-center gap-3 lg:hidden">
        <button
          onClick={onMenuClick}
          className="p-2 rounded-lg hover:bg-neutral-100"
          aria-label="Open menu"
        >
          <Menu className="w-6 h-6 text-neutral-600" />
        </button>
      </div>

      {/* Center: Title & Pipeline Status */}
      <div className="hidden lg:flex flex-1 items-center justify-center gap-6">
        <h1 className="text-xl font-semibold text-neutral-900">MFD Fund Monitor</h1>
        
        <div className="flex items-center gap-4">
          {/* Pipeline Status */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-neutral-50">
            <span
              className={cn(
                'w-2 h-2 rounded-full',
                health ? statusColors[statusTone] : 'bg-neutral-400'
              )}
            />
            <span className="text-sm font-medium text-neutral-700">
              {health ? statusLabels[statusTone] : 'Loading...'}
            </span>
          </div>

          {/* Data Freshness */}
          {health && (
            <div className="flex items-center gap-2 text-sm text-neutral-500">
              <span>NAV:</span>
              <time dateTime={health.latest_nav_date}>
                {health.latest_nav_date ? new Date(health.latest_nav_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '—'}
              </time>
              <span className="text-neutral-300">|</span>
              <span>Scores:</span>
              <time dateTime={health.latest_score_date}>
                {health.latest_score_date ? new Date(health.latest_score_date).toLocaleDateString('en-IN', { day: '2-digit', month: 'short' }) : '—'}
              </time>
            </div>
          )}
        </div>
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-2">
        {/* Notifications */}
        <div className="relative">
          <button
            onClick={() => setShowNotifications(!showNotifications)}
            className="relative p-2 rounded-lg hover:bg-neutral-100"
            aria-label="Notifications"
            aria-expanded={showNotifications}
          >
            <Bell className="w-5 h-5 text-neutral-600" />
            <span className="absolute -top-1 -right-1 w-4 h-4 bg-danger-500 text-white text-[10px] font-bold rounded-full flex items-center justify-center">
              3
            </span>
          </button>

          {showNotifications && (
            <div className="absolute right-0 mt-2 w-80 bg-white rounded-xl shadow-lg border border-neutral-200 py-2 z-50">
              <div className="px-4 py-2 border-b border-neutral-100 flex items-center justify-between">
                <h3 className="font-semibold text-neutral-900">Notifications</h3>
                <button className="text-sm text-primary-600 hover:text-primary-700">Mark all read</button>
              </div>
              <div className="max-h-64 overflow-y-auto">
                <div className="px-4 py-3 border-b border-neutral-100">
                  <p className="text-sm font-medium text-neutral-900">High drawdown alert</p>
                  <p className="text-xs text-neutral-500">HDFC Top 100 - Max DD 22%</p>
                  <p className="text-xs text-neutral-400 mt-1">10 minutes ago</p>
                </div>
                <div className="px-4 py-3 border-b border-neutral-100">
                  <p className="text-sm font-medium text-neutral-900">Rank decline</p>
                  <p className="text-xs text-neutral-500">SBI Small Cap - Dropped 15 positions</p>
                  <p className="text-xs text-neutral-400 mt-1">1 hour ago</p>
                </div>
                <div className="px-4 py-3">
                  <p className="text-sm font-medium text-neutral-900">Benchmark deviation</p>
                  <p className="text-xs text-neutral-500">ICICI Pru Large & Mid Cap - Alpha -6%</p>
                  <p className="text-xs text-neutral-400 mt-1">3 hours ago</p>
                </div>
              </div>
              <div className="px-4 py-2 border-t border-neutral-100">
                <Link href="/alerts" className="text-sm text-primary-600 hover:text-primary-700 block text-center">
                  View all alerts
                </Link>
              </div>
            </div>
          )}
        </div>

        {/* Refresh */}
        <button
          className="p-2 rounded-lg hover:bg-neutral-100"
          aria-label="Refresh data"
        >
          <RefreshCw className="w-5 h-5 text-neutral-600" />
        </button>

        {/* User Menu */}
        <div className="relative">
          <button
            className="flex items-center gap-2 p-2 rounded-lg hover:bg-neutral-100"
            aria-label="User menu"
          >
            <div className="w-8 h-8 rounded-full bg-neutral-200 flex items-center justify-center">
              <svg className="w-5 h-5 text-neutral-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M16 7a4 4 0 11-8 0 4 4 0 018 0zM12 14a7 7 0 00-7 7h18a7 7 0 00-7-7z" />
              </svg>
            </div>
            <span className="hidden sm:block text-sm font-medium text-neutral-700">MFD User</span>
            <ChevronDown className="w-4 h-4 text-neutral-500" />
          </button>
        </div>
      </div>
    </header>
  );
}