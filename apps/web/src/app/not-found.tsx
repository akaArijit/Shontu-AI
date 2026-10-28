import Link from 'next/link';
import { SearchX } from 'lucide-react';

export default function NotFound() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-neutral-50 px-4">
      <div className="w-full max-w-md rounded-xl border border-neutral-200 bg-white p-8 text-center shadow-card">
        <div className="mx-auto mb-4 flex h-12 w-12 items-center justify-center rounded-full bg-primary-50">
          <SearchX className="h-6 w-6 text-primary-600" aria-hidden="true" />
        </div>
        <h1 className="text-lg font-semibold text-neutral-900">Page not found</h1>
        <p className="mt-2 text-sm text-neutral-600">
          That page does not exist in the fund monitoring dashboard.
        </p>
        <Link
          href="/dashboard"
          className="mt-6 inline-flex items-center rounded-lg bg-primary-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-primary-500 focus:ring-offset-2"
        >
          Back to dashboard
        </Link>
      </div>
    </div>
  );
}
