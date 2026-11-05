"use client";

import Badge from "@/components/Badge";
import type {
  FileReport,
  ImportIssue,
  PreviewResponse,
  SectionDetails,
} from "@/lib/types";

function formatDate(value: string | null): string {
  if (!value) return "Not found";
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function SectionMapping({
  title,
  details,
}: {
  title: string;
  details: SectionDetails | null;
}) {
  if (!details || details.not_supplied) {
    return (
      <div className="panel-muted p-4">
        <h4 className="text-sm font-semibold text-parchment-200">{title}</h4>
        <p className="mt-1 text-xs text-parchment-400">Not supplied.</p>
      </div>
    );
  }

  return (
    <div className="panel-muted p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h4 className="text-sm font-semibold text-parchment-200">{title}</h4>
        {details.missing_required.length > 0 ? (
          <Badge tone="red">Missing required columns</Badge>
        ) : details.headerless ? (
          <Badge tone="amber">Fixed 13-column layout</Badge>
        ) : (
          <Badge tone="blue">Required columns found</Badge>
        )}
      </div>
      <p className="mt-1 text-[11px] text-parchment-400">
        {details.headerless ? "Header row: not supplied" : `Sheet: ${details.sheet ?? "not found"}`}
        {details.header_row ? ` · header row ${details.header_row}` : ""}
        {details.source_kind ? ` · ${details.source_kind.toUpperCase()}` : ""}
      </p>
      {details.layout_warning && (
        <p className="mt-2 text-xs text-amber-300">{details.layout_warning}</p>
      )}
      <dl className="mt-3 max-h-48 space-y-1 overflow-auto text-xs">
        {Object.entries(details.mapping).map(([internal, source]) => (
          <div key={internal} className="flex gap-1">
            <dt className="min-w-[120px] font-medium text-parchment-400">{internal}:</dt>
            <dd className="truncate text-parchment-400">{source}</dd>
          </div>
        ))}
      </dl>
      {details.missing_required.length > 0 && (
        <p className="mt-3 text-xs font-medium text-rose-300">
          Missing: {details.missing_required.join(", ")}
        </p>
      )}
      {details.ignored_sensitive_columns.length > 0 && (
        <p className="mt-2 text-xs text-amber-300">
          Ignored sensitive columns: {details.ignored_sensitive_columns.join(", ")}
        </p>
      )}
      {details.unmapped_columns.length > 0 && (
        <p className="mt-2 text-xs text-parchment-400">
          Other columns: {details.unmapped_columns.join(", ")}
        </p>
      )}
    </div>
  );
}

function IssueList({
  issues,
  total,
}: {
  issues: ImportIssue[];
  total: number;
}) {
  if (issues.length === 0) {
    return <p className="mt-2 text-xs text-parchment-400">No row issues detected.</p>;
  }
  return (
    <ul className="mt-2 max-h-72 space-y-2 overflow-auto text-xs">
      {issues.slice(0, 100).map((item, index) => (
        <li
          key={`${item.file_type}-${item.row_number}-${index}`}
          className={
            item.severity === "error"
              ? "text-rose-300"
              : item.severity === "warning"
                ? "text-amber-300"
                : "text-parchment-400"
          }
        >
          <span className="font-medium">
            {item.file_type}
            {item.row_number ? ` · row ${item.row_number}` : ""}
          </span>
          {item.field ? ` · ${item.field}` : ""}: {item.message}
        </li>
      ))}
      {total > 100 && (
        <li className="text-parchment-400">
          Showing 100 of {total.toLocaleString("en-IN")} issues. The stored
          preview and row counts include every issue.
        </li>
      )}
    </ul>
  );
}

function FileReportTable({
  reports,
}: {
  reports: Record<string, FileReport>;
}) {
  const rows = ["clients", "folios", "portfolio", "transactions"]
    .map((key) => reports[key])
    .filter(Boolean);
  if (rows.length === 0) return null;

  return (
    <div className="mt-4 overflow-hidden rounded-xl border border-warm-100/15">
      <table className="min-w-full text-left text-xs">
        <thead className="bg-parchment-50/[0.04] text-[10px] uppercase tracking-[0.12em] text-parchment-500">
          <tr>
            <th className="px-3 py-2 font-semibold">File</th>
            <th className="px-3 py-2 text-right font-semibold">Rows read</th>
            <th className="px-3 py-2 text-right font-semibold">Imported</th>
            <th className="px-3 py-2 text-right font-semibold">Matched</th>
            <th className="px-3 py-2 text-right font-semibold">Skipped</th>
            <th className="px-3 py-2 font-semibold">Reasons and warnings</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-warm-100/10 text-parchment-300">
          {rows.map((report) => {
            const reasons = report.reasons
              .map((reason) => `${reason.count.toLocaleString("en-IN")} ${reason.label}`)
              .join(", ");
            const retained =
              report.invalid_date_rows || report.invalid_number_rows
                ? [
                    report.invalid_date_rows
                      ? `${report.invalid_date_rows.toLocaleString("en-IN")} row(s) with unreadable dates`
                      : null,
                    report.invalid_number_rows
                      ? `${report.invalid_number_rows.toLocaleString("en-IN")} row(s) with unreadable amounts/numbers`
                      : null,
                  ]
                    .filter(Boolean)
                    .join(", ")
                : "";
            return (
              <tr key={report.file_type}>
                <td className="px-3 py-2">
                  <span className="font-medium text-parchment-200">
                    {report.label}
                  </span>
                  <span className="mt-1 block">
                    {report.supplied ? (
                      report.header_ok ? (
                        <Badge tone="blue">Headers found</Badge>
                      ) : (
                        <Badge tone="red">Headers missing</Badge>
                      )
                    ) : (
                      <Badge tone="slate">Not supplied</Badge>
                    )}
                  </span>
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {report.rows_read.toLocaleString("en-IN")}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {report.imported_rows.toLocaleString("en-IN")}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {report.matched_rows === null
                    ? "—"
                    : report.matched_rows.toLocaleString("en-IN")}
                </td>
                <td className="px-3 py-2 text-right tabular-nums">
                  {report.skipped_rows.toLocaleString("en-IN")}
                </td>
                <td className="px-3 py-2">
                  {report.message}
                  {reasons ? (
                    <span className="mt-1 block text-parchment-400">
                      Skipped: {reasons}.
                    </span>
                  ) : null}
                  {retained ? (
                    <span className="mt-1 block text-amber-300">
                      Retained for review: {retained}. These are excluded from
                      calculations and shown as Not available.
                    </span>
                  ) : null}
                  {report.unmatched_rows ? (
                    <span className="mt-1 block text-amber-300">
                      {report.unmatched_rows.toLocaleString("en-IN")} row(s)
                      could not be matched to a client or folio.
                    </span>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

export default function PreviewPanel({
  preview,
  busy,
  onConfirm,
  onCancel,
}: {
  preview: PreviewResponse;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const { counts, file_reports: fileReports, client_matching: matching } = preview;

  const countCards = [
    ["Clients", counts.clients_imported, fileReports.clients?.rows_read ?? null],
    ["Folios", counts.folios_imported, fileReports.folios?.rows_read ?? null],
    [
      "Portfolio rows",
      counts.portfolio_imported,
      fileReports.portfolio?.rows_read ?? null,
    ],
    [
      "Transactions",
      counts.transactions_imported,
      fileReports.transactions?.rows_read ?? null,
    ],
    ["Needs review", counts.needs_review, counts.schemes],
    ["Unmatched folios", counts.unmatched_folios, null],
    ["Unmatched transactions", counts.transactions_unmatched, null],
    ["Switch reviews", counts.switch_reviews, null],
    ["Reconciliation warnings", counts.reconciliation_warnings, null],
  ];

  return (
    <section className="panel border-copper-400/25 bg-ink-800 p-5">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-parchment-100">
            Review before saving
          </h2>
          <p className="mt-1 text-sm text-parchment-400">
            No data has been saved yet. Check the detected columns, valuation date
            and skipped rows. Confirming replaces the current local snapshot.
          </p>
        </div>
        <Badge tone={preview.can_confirm ? "green" : "red"}>
          {preview.can_confirm ? "Ready to import" : "Fix the files first"}
        </Badge>
      </div>

      <div className="panel-inset mt-4 p-3 text-sm">
        <span className="font-medium text-parchment-200">Valuation date: </span>
        <span className="text-parchment-300">{formatDate(preview.report_date)}</span>
        <span className="ml-2 text-xs text-parchment-400">
          from the Portfolio Valuation report date
        </span>
      </div>

      <div className="mt-3 grid gap-3 lg:grid-cols-2">
        <div
          className={
            preview.export_run.status === "review"
              ? "rounded-xl border border-amber-400/30 bg-amber-400/[0.06] p-3 text-xs text-amber-200"
              : "panel-muted p-3 text-xs text-parchment-400"
          }
        >
          <p className="font-semibold text-parchment-200">Export run check</p>
          <p className="mt-1">{preview.export_run.message}</p>
        </div>
        <div
          className={
            matching.status === "review"
              ? "rounded-xl border border-amber-400/30 bg-amber-400/[0.06] p-3 text-xs text-amber-200"
              : "panel-muted p-3 text-xs text-parchment-400"
          }
        >
          <p className="font-semibold text-parchment-200">Client matching</p>
          <p className="mt-1">{matching.message}</p>
          <p className="mt-1">
            Folios {matching.folios.matched ?? 0}/{matching.folios.total} ·
            Portfolio {matching.portfolio.matched ?? 0}/
            {matching.portfolio.total}
            {matching.transactions
              ? ` · Transactions ${matching.transactions.matched ?? 0}/${
                  matching.transactions.total
                }`
              : ""}
          </p>
        </div>
      </div>

      <div className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
        {countCards.map(([label, imported, total]) => (
          <div
            key={String(label)}
            className="rounded-xl border border-warm-100/15 bg-parchment-50/[0.04] p-3"
          >
            <p className="eyebrow">{label}</p>
            <p className="mt-1 text-xl font-semibold text-parchment-100">{imported}</p>
            {total !== null && (
              <p className="mt-1 text-[11px] text-parchment-400">of {total} rows</p>
            )}
          </div>
        ))}
      </div>

      <FileReportTable reports={fileReports} />

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <SectionMapping
          title="Client Details columns"
          details={preview.detected_columns.clients}
        />
        <SectionMapping
          title="Folios columns"
          details={preview.detected_columns.folios}
        />
        <SectionMapping
          title="Portfolio Valuation columns"
          details={preview.detected_columns.portfolio}
        />
        <SectionMapping
          title="Transaction Statement columns"
          details={preview.detected_columns.transactions}
        />
      </div>

      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        <div className="panel-muted p-4">
          <h4 className="text-sm font-semibold text-parchment-200">
            Rows needing attention
          </h4>
          <IssueList
            issues={preview.issues}
            total={preview.issue_count ?? preview.issues.length}
          />
        </div>
        <div className="panel-muted p-4">
          <h4 className="text-sm font-semibold text-parchment-200">
            What will be saved
          </h4>
          <ul className="mt-2 space-y-1 text-xs text-parchment-400">
            {preview.warnings.map((warning, index) => (
              <li key={`${warning}-${index}`}>• {warning}</li>
            ))}
          </ul>
          {preview.sample_folios.length > 0 && (
            <div className="mt-3 border-t border-warm-100/15 pt-2">
              <p className="eyebrow">Sample folios</p>
              <ul className="mt-1 space-y-1 text-xs text-parchment-400">
                {preview.sample_folios.slice(0, 5).map((folio, index) => (
                  <li key={`${folio.folio_number}-${index}`}>
                    {folio.folio_number} · {folio.scheme_name} ·{" "}
                    {folio.client_name}
                  </li>
                ))}
              </ul>
            </div>
          )}
          {counts.errors > 0 && (
            <p className="mt-3 text-xs font-medium text-rose-300">
              {counts.errors.toLocaleString("en-IN")} blocking error(s) must be
              fixed before confirming.
            </p>
          )}
        </div>
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          className="btn-primary"
          disabled={!preview.can_confirm || busy}
          onClick={onConfirm}
          title={
            busy
              ? "Wait for the current import to finish"
              : preview.can_confirm
                ? "Save this preview and replace the current local snapshot"
                : "Fix the blocking file errors before confirming"
          }
          type="button"
        >
          {busy ? "Saving…" : "Confirm import and replace snapshot"}
        </button>
        <button
          className="btn-secondary"
          disabled={busy}
          onClick={onCancel}
          title={
            busy
              ? "Wait for the current import to finish"
              : "Discard this preview without saving"
          }
          type="button"
        >
          Cancel
        </button>
        <span className="text-xs text-parchment-400">
          Preview ID:{" "}
          <span className="font-mono text-parchment-400">{preview.import_id.slice(0, 12)}…</span>
        </span>
      </div>
    </section>
  );
}
