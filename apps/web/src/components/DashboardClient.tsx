"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import AppNav from "@/components/AppNav";
import ImportProgress from "@/components/ImportProgress";
import PreviewPanel from "@/components/PreviewPanel";
import UploadPanel from "@/components/UploadPanel";
import { api } from "@/lib/api";
import type { DashboardResponse, PreviewResponse } from "@/lib/types";
import { validateUploadFile } from "@/lib/upload";

function formatDate(value: string | null): string {
  if (!value) return "Not available";
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatCount(value: number): string {
  return value.toLocaleString("en-IN");
}

function SnapshotStat({
  label,
  value,
  note,
}: {
  label: string;
  value: string;
  note?: string;
}) {
  return (
    <div className="min-w-[116px]">
      <dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-parchment-500">
        {label}
      </dt>
      <dd className="mt-1 text-sm font-semibold tabular-nums text-parchment-100">
        {value}
      </dd>
      {note && (
        <dd className="mt-0.5 text-[11px] text-parchment-400">{note}</dd>
      )}
    </div>
  );
}

export default function DashboardClient() {
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [preview, setPreview] = useState<PreviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [confirmDemo, setConfirmDemo] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [operation, setOperation] = useState<
    "preview" | "confirm" | "demo" | null
  >(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.dashboard();
      setDashboard(data);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? `${err.message}. Make sure the local API is running at ${api.baseUrl}.`
          : "Could not load the dashboard.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    if (!confirmDemo) return;

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setConfirmDemo(false);
    }

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [confirmDemo]);

  async function handlePreview(
    clients: File,
    folios: File,
    portfolio: File,
    transactions: File,
  ) {
    const fileError = [clients, folios, portfolio, transactions]
      .map((file) => validateUploadFile(file))
      .find(Boolean);
    if (fileError) {
      setError(fileError);
      setNotice(null);
      return;
    }

    setBusy(true);
    setOperation("preview");
    setError(null);
    setNotice(null);
    try {
      const formData = new FormData();
      formData.append("clients_file", clients);
      formData.append("folios_file", folios);
      formData.append("portfolio_file", portfolio);
      formData.append("transactions_file", transactions);
      const result = await api.previewImport(formData);
      setPreview(result);
      const skipped =
        result.counts.clients_skipped +
        result.counts.folios_skipped +
        result.counts.portfolio_skipped +
        result.counts.transaction_skipped;
      setNotice(
        result.can_confirm
          ? `Preview ready: ${result.counts.transactions_imported.toLocaleString(
              "en-IN",
            )} transaction(s) matched or retained, ${skipped.toLocaleString(
              "en-IN",
            )} skipped row(s). Review the file summary and issues before confirming.`
          : "Preview has blocking errors. Fix the files and try again.",
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not preview these files.",
      );
    } finally {
      setBusy(false);
      setOperation(null);
    }
  }

  async function handleConfirm() {
    if (!preview) return;
    setBusy(true);
    setOperation("confirm");
    setError(null);
    try {
      const result = await api.confirmImport(preview.import_id);
      setPreview(null);
      setNotice(
        `Snapshot saved: ${result.imported.clients} client(s), ${result.imported.folios} folio(s), ${result.imported.portfolio_rows} portfolio row(s), ${result.imported.transactions} transaction(s). ${result.imported.needs_review} benchmark mapping${result.imported.needs_review === 1 ? "" : "s"} ${result.imported.needs_review === 1 ? "needs" : "need"} review; ${result.reconciliation_warnings} reconciliation warning${result.reconciliation_warnings === 1 ? "" : "s"}.`,
      );
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not confirm the import.");
    } finally {
      setBusy(false);
      setOperation(null);
    }
  }

  async function loadDemo(replace: boolean) {
    setBusy(true);
    setOperation("demo");
    setError(null);
    setNotice(null);
    try {
      const result = await api.loadDemo(replace);
      setPreview(null);
      setNotice(
        `Demo snapshot loaded: ${result.imported.clients} clients, ${result.imported.folios} folios, ${result.imported.portfolio_rows} portfolio rows, ${result.imported.transactions} transactions. ${result.imported.needs_review} mappings need review.`,
      );
      await refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load demo data.");
    } finally {
      setBusy(false);
      setOperation(null);
    }
  }

  async function resetData() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.resetData();
      setPreview(null);
      // Full reload so every page (Benchmark Data, Graph) re‑fetches empty snapshot
      window.location.reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not delete data.");
    } finally {
      setBusy(false);
      setConfirmDelete(false);
    }
  }

  function handleDemo() {
    const hasData = (dashboard?.summary.folios ?? 0) > 0;
    if (hasData) {
      setConfirmDemo(true);
      return;
    }
    void loadDemo(false);
  }

  const summary = dashboard?.summary;
  const hasData = (summary?.folios ?? 0) > 0;
  const mappingsReady = summary?.benchmark_reviewed ?? 0;
  const mappingsNeedReview = summary?.needs_review ?? 0;
  const warnings: string[] = [];

  if (hasData && summary) {
    if (mappingsNeedReview > 0) {
      warnings.push(
        `${mappingsNeedReview} benchmark mapping${mappingsNeedReview === 1 ? "" : "s"} still ${mappingsNeedReview === 1 ? "needs" : "need"} review.`,
      );
    }
    if (summary.benchmark_levels_missing > 0) {
      warnings.push(
        `${summary.benchmark_levels_missing} folio${summary.benchmark_levels_missing === 1 ? "" : "s"} ${summary.benchmark_levels_missing === 1 ? "has" : "have"} reviewed mapping but incomplete local benchmark dates. Open Benchmark Data to see the exact missing dates.`,
      );
    }
    if (summary.unmatched_folios > 0) {
      warnings.push(
        `${summary.unmatched_folios} folio${summary.unmatched_folios === 1 ? "" : "s"} could not be matched to a client.`,
      );
    }
    if (summary.reconciliation_warnings > 0) {
      warnings.push(
        `${summary.reconciliation_warnings} reconciliation warning${summary.reconciliation_warnings === 1 ? "" : "s"} ${summary.reconciliation_warnings === 1 ? "remains" : "remain"}.`,
      );
    }
  }

  return (
    <main className="mx-auto w-full max-w-[1180px] px-4 py-6 sm:px-6 lg:px-8">
      <header className="mb-6">
        <div className="mb-3">
          <AppNav active="upload" />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight text-parchment-50 sm:text-3xl">
            MFD Portfolio Dashboard
          </h1>
          <span className="rounded-full bg-sage-500/10 px-2.5 py-1 text-[11px] font-semibold text-sage-300 ring-1 ring-inset ring-sage-500/25">
            Local only
          </span>
        </div>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-parchment-400">
          Upload the four InvestWell exports, review the snapshot, then open the
          benchmark graph. Detailed portfolio analytics stay in InvestWell; this
          app keeps only the local import and graph workflow.
        </p>
      </header>

      {error && (
        <div className="mb-4 rounded-xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      )}
      {notice && (
        <div className="mb-4 rounded-xl border border-copper-400/25 bg-copper-400/[0.08] px-4 py-3 text-sm text-copper-200">
          {notice}
        </div>
      )}

      {operation && (
        <div className="mb-4">
          <ImportProgress kind={operation} />
        </div>
      )}

      <div className="space-y-5">
        <section className="glass-panel overflow-hidden p-5">
          <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="eyebrow">Current snapshot</p>
              <div className="mt-1.5 flex flex-wrap items-center gap-2">
                <h2 className="text-xl font-semibold tracking-tight text-parchment-50">
                  {loading && !dashboard
                    ? "Checking local snapshot…"
                    : hasData
                      ? "Snapshot ready"
                      : "No snapshot imported"}
                </h2>
                <span
                  className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ring-1 ring-inset ${
                    hasData
                      ? "bg-copper-400/10 text-copper-300 ring-copper-400/25"
                      : "bg-parchment-50/[0.06] text-parchment-400 ring-warm-100/15"
                  }`}
                >
                  {hasData ? "Graph available" : "Upload required"}
                </span>
              </div>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-parchment-400">
                {hasData
                  ? `Latest valuation date: ${formatDate(dashboard?.meta.valuation_date ?? null)}. The graph uses the reviewed mappings and locally imported benchmark levels.`
                  : "Import all four files below, or load the demo snapshot to explore the graph. Nothing leaves this laptop."}
              </p>
            </div>
            {hasData && (
              <div className="flex shrink-0 flex-wrap gap-2">
                <Link className="btn-primary px-4 py-2 text-sm" href="/graph">
                  Open Graph
                </Link>
                <Link
                  className="btn-secondary px-4 py-2 text-sm"
                  href="/benchmarks"
                >
                  Benchmark Data
                </Link>
              </div>
            )}
          </div>

          {hasData && summary && (
            <dl className="mt-5 flex flex-wrap gap-x-8 gap-y-4 border-t border-warm-100/15 pt-4">
              <SnapshotStat
                label="Clients"
                value={formatCount(summary.clients)}
              />
              <SnapshotStat
                label="Folios"
                value={formatCount(summary.folios)}
              />
              <SnapshotStat
                label="Transactions"
                value={formatCount(summary.transactions)}
              />
              <SnapshotStat
                label="Mappings reviewed"
                note={
                  mappingsNeedReview > 0
                    ? `${mappingsNeedReview} ${mappingsNeedReview === 1 ? "needs" : "need"} review`
                    : "All reviewed"
                }
                value={formatCount(mappingsReady)}
              />
              <SnapshotStat
                label="Comparisons ready"
                note="Folios with a local comparison"
                value={formatCount(
                  summary.benchmark_comparisons_available,
                )}
              />
            </dl>
          )}

          {warnings.length > 0 && (
            <div className="mt-4 rounded-xl border border-amber-400/25 bg-amber-400/[0.06] px-3.5 py-3 text-xs">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-semibold text-amber-200">Needs attention</p>
                {mappingsNeedReview > 0 && (
                  <Link
                    className="font-medium text-amber-200 underline decoration-amber-400/40 underline-offset-2 hover:text-amber-100"
                    href="/benchmarks"
                  >
                    Review benchmark data
                  </Link>
                )}
              </div>
              <ul className="mt-1.5 space-y-1 text-amber-100/80">
                {warnings.map((warning) => (
                  <li key={warning}>• {warning}</li>
                ))}
              </ul>
            </div>
          )}
        </section>

        <UploadPanel
          busy={busy}
          hasData={hasData}
          onDemo={handleDemo}
          onPreview={handlePreview}
        />

        {hasData && (
          <section className="panel p-5 border border-rose-400/25 bg-rose-500/05">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <h3 className="text-base font-semibold text-rose-200">Danger zone</h3>
                <p className="mt-1 text-sm text-rose-100/80">
                  This permanently deletes the current local snapshot (clients, folios,
                  transactions, portfolio valuation, scheme mappings and benchmark
                  levels). It cannot be undone.
                </p>
              </div>
              <button
                className="btn-primary bg-rose-500 hover:bg-rose-600 border-rose-400/30 text-rose-50 self-start"
                disabled={busy}
                onClick={() => setConfirmDelete(true)}
                type="button"
              >
                Delete current data
              </button>
            </div>
          </section>
        )}

        {preview && (
          <PreviewPanel
            busy={busy}
            onCancel={() => setPreview(null)}
            onConfirm={handleConfirm}
            preview={preview}
          />
        )}
      </div>

      <footer className="mt-8 border-t border-warm-100/15 pt-4 text-xs leading-5 text-parchment-400">
        Data stays in{" "}
        <code className="rounded bg-parchment-50/[0.06] px-1 py-0.5 text-parchment-400">
          data/local/mfd.sqlite3
        </code>
        . Original XLSX/CSV files are not retained, and no data is sent to a
        cloud service.
      </footer>

      {confirmDemo && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#0b0908]/80 p-4 backdrop-blur-sm"
          role="presentation"
          onClick={() => setConfirmDemo(false)}
        >
          <div
            aria-labelledby="demo-confirm-title"
            aria-modal="true"
            className="glass-dialog w-full max-w-md p-6"
            role="dialog"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start gap-3">
              <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-amber-400/10 text-sm font-semibold text-amber-300 ring-1 ring-inset ring-amber-400/25">
                !
              </span>
              <div>
                <h2
                  className="text-base font-semibold text-parchment-100"
                  id="demo-confirm-title"
                >
                  Replace local snapshot?
                </h2>
                <p className="mt-2 text-sm leading-6 text-parchment-400">
                  Loading demo data will replace all currently imported local data
                  with the synthetic demo snapshot. This cannot be undone.
                </p>
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button
                autoFocus
                className="btn-secondary"
                onClick={() => setConfirmDemo(false)}
                type="button"
              >
                Cancel
              </button>
              <button
                className="btn-primary"
                disabled={busy}
                onClick={() => {
                  setConfirmDemo(false);
                  void loadDemo(true);
                }}
                title={
                  busy
                    ? "Wait for the current operation to finish"
                    : "Replace the local snapshot with demo data"
                }
                type="button"
              >
                Replace with demo
              </button>
            </div>
          </div>
        </div>
      )}
      {confirmDelete && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-[#0b0908]/80 p-4 backdrop-blur-sm"
          role="presentation"
          onClick={() => setConfirmDelete(false)}
        >
          <div
            aria-labelledby="delete-confirm-title"
            aria-modal="true"
            className="glass-dialog w-full max-w-md p-6"
            role="dialog"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="flex items-start gap-3">
              <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-rose-400/10 text-sm font-semibold text-rose-300 ring-1 ring-inset ring-rose-400/25">
                !
              </span>
              <div>
                <h2
                  className="text-base font-semibold text-parchment-100"
                  id="delete-confirm-title"
                >
                  Delete current data?
                </h2>
                <p className="mt-2 text-sm leading-6 text-parchment-400">
                  This will permanently delete the current local dashboard data.
                  This cannot be undone.
                </p>
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-2">
              <button
                autoFocus
                className="btn-secondary"
                onClick={() => setConfirmDelete(false)}
                type="button"
              >
                Cancel
              </button>
              <button
                className="btn-primary bg-rose-500 hover:bg-rose-600 border-rose-400/30"
                disabled={busy}
                onClick={() => {
                  setConfirmDelete(false);
                  void resetData();
                }}
                title={busy ? "Wait for the current operation to finish" : "Delete all local snapshot data"}
                type="button"
              >
                Delete current data
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
