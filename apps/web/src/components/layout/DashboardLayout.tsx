'use client';

import { useState } from 'react';
import { AlertTriangle } from 'lucide-react';
import { Sidebar } from './Sidebar';
import { Header } from './Header';
import { usePipelineHealth } from '@/hooks/useQueries';
import { cn } from '@/lib/utils';

export function DashboardLayout({ children }: { children: React.ReactNode }) {
  const [sidebarCollapsed, setSidebarCollapsed] = useState(false);
  const [isMobile, setIsMobile] = useState(false);
  const { isError: apiUnreachable } = usePipelineHealth();

  return (
    <div className="min-h-screen bg-neutral-50">
      <Sidebar collapsed={sidebarCollapsed} onToggle={() => setSidebarCollapsed(!sidebarCollapsed)} />
      <Header onMenuClick={() => setSidebarCollapsed(!sidebarCollapsed)} sidebarCollapsed={sidebarCollapsed} />

      <main
        className={cn(
          'min-h-screen pt-16 transition-all duration-300',
          sidebarCollapsed ? 'lg:ml-16' : 'lg:ml-64'
        )}
        id="main-content"
        role="main"
      >
        {apiUnreachable ? (
          <div
            role="alert"
            className="mx-4 mt-4 flex items-start gap-3 rounded-lg border border-danger-100 bg-danger-50 p-4 text-sm text-danger-600 lg:mx-6"
          >
            <AlertTriangle className="mt-0.5 h-5 w-5 flex-shrink-0" aria-hidden="true" />
            <div>
              <p className="font-medium">Cannot reach the fund engine API</p>
              <p className="mt-1 text-danger-600">
                Check that <code className="font-mono">NEXT_PUBLIC_API_URL</code>{' '}
                points at the Railway API and that its{' '}
                <code className="font-mono">ALLOWED_ORIGINS</code> includes this
                site, then redeploy the dashboard.
              </p>
            </div>
          </div>
        ) : null}

        <div className="p-4 lg:p-6">
          {children}
        </div>
      </main>
    </div>
  );
}