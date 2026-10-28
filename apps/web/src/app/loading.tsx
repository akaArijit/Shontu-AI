export default function Loading() {
  return (
    <div className="flex min-h-[60vh] items-center justify-center" role="status" aria-live="polite">
      <div className="flex flex-col items-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-neutral-200 border-t-primary-600" />
        <span className="text-sm text-neutral-500">Loading dashboard…</span>
      </div>
    </div>
  );
}
