"use client";

import { useState } from "react";
import {
  formatFileSize,
  MAX_UPLOAD_LABEL,
  validateUploadFile,
} from "@/lib/upload";

type FileSlot = "clients" | "folios" | "portfolio" | "transactions";

const SLOTS: {
  key: FileSlot;
  label: string;
  hint: string;
  fileNameHint: string;
}[] = [
  {
    key: "clients",
    label: "Client Details",
    hint: "Client master used to identify and group folios.",
    fileNameHint: "Client Details-27-10-2026-...xlsx / .csv",
  },
  {
    key: "folios",
    label: "Folios",
    hint: "Folio, scheme, units and folio-level AUM.",
    fileNameHint: "Folios-27-10-2026-...xlsx / .csv",
  },
  {
    key: "portfolio",
    label: "Portfolio Valuation",
    hint: "Client-level current value, gains and report date. The fixed 13-column CSV layout is accepted with a warning.",
    fileNameHint: "PortfolioValuationReportMF-27-10-2026-...xlsx / .csv",
  },
  {
    key: "transactions",
    label: "Transaction Statement",
    hint: "Dated purchases, SIPs, redemptions and switches for folio returns.",
    fileNameHint: "Transaction Statement for Mutual Funds-...xlsx / .csv",
  },
];

export default function UploadPanel({
  busy,
  hasData,
  onPreview,
  onDemo,
}: {
  busy: boolean;
  hasData: boolean;
  onPreview: (
    clients: File,
    folios: File,
    portfolio: File,
    transactions: File,
  ) => void;
  onDemo: () => void;
}) {
  const [files, setFiles] = useState<Record<FileSlot, File | null>>({
    clients: null,
    folios: null,
    portfolio: null,
    transactions: null,
  });

  const fileErrors = Object.fromEntries(
    SLOTS.map((slot) => [
      slot.key,
      files[slot.key] ? validateUploadFile(files[slot.key]!) : null,
    ]),
  ) as Record<FileSlot, string | null>;
  const hasFileError = Object.values(fileErrors).some(Boolean);
  const ready = Boolean(
    files.clients &&
      files.folios &&
      files.portfolio &&
      files.transactions &&
      !hasFileError,
  );
  const totalSize = Object.values(files).reduce(
    (total, file) => total + (file?.size ?? 0),
    0,
  );

  function setFile(key: FileSlot, file: File | null) {
    setFiles((current) => ({ ...current, [key]: file }));
  }

  return (
    <section className="panel p-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <h2 className="text-base font-semibold text-parchment-100">
            Import the four InvestWell files
          </h2>
          <p className="mt-1 max-w-3xl text-sm text-parchment-400">
            Select the Client Details, Folios, Portfolio Valuation and Transaction
            Statement exports from the same export run. XLSX and CSV are accepted.
            All four are required here because transaction data drives folio returns.
            Nothing is saved until you review the preview and confirm it.
          </p>
        </div>
        <button
          className="btn-secondary self-start"
          disabled={busy}
          onClick={onDemo}
          title={
            busy
              ? "Wait for the current file operation to finish"
              : hasData
                ? "Replace the local snapshot with demo data"
                : "Load the local demo snapshot"
          }
          type="button"
        >
          {hasData ? "Replace with demo data" : "Load demo data"}
        </button>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {SLOTS.map((slot) => (
          <label
            key={slot.key}
            className="rounded-xl border border-dashed border-warm-100/20 bg-parchment-50/[0.03] p-4 transition-colors hover:border-copper-400/40 hover:bg-copper-400/[0.03]"
          >
            <span className="block text-sm font-medium text-parchment-200">
              {slot.label} <span className="text-copper-300">*</span>
            </span>
            <span className="mt-1 block text-xs text-parchment-400">{slot.hint}</span>
            <input
              className="mt-3 block w-full cursor-pointer rounded-lg border border-warm-100/15 bg-ink-900 px-3 py-2 text-sm text-parchment-300 file:mr-3 file:rounded-md file:border-0 file:bg-copper-500/15 file:px-3 file:py-1.5 file:text-xs file:font-semibold file:text-copper-200 hover:file:bg-copper-500/25"
              type="file"
              accept=".xlsx,.csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,text/csv"
              onChange={(event) => setFile(slot.key, event.target.files?.[0] ?? null)}
            />
            <span
              className="mt-2 block truncate text-xs text-parchment-400"
              title={files[slot.key]?.name ?? slot.fileNameHint}
            >
              {files[slot.key]?.name ?? slot.fileNameHint}
            </span>
            {files[slot.key] ? (
              <span className="mt-1 block text-[11px] text-parchment-500">
                {formatFileSize(files[slot.key]!.size)}
                {files[slot.key]!.size > 5 * 1024 * 1024
                  ? " · large file, processing may take longer"
                  : ""}
              </span>
            ) : null}
            {fileErrors[slot.key] ? (
              <span className="mt-2 block text-xs text-rose-300">
                {fileErrors[slot.key]}
              </span>
            ) : null}
          </label>
        ))}
      </div>

      <div className="mt-4 flex flex-wrap items-center gap-3">
        <button
          className="btn-primary"
          disabled={!ready || busy}
          onClick={() => {
            if (
              files.clients &&
              files.folios &&
              files.portfolio &&
              files.transactions
            ) {
              onPreview(
                files.clients,
                files.folios,
                files.portfolio,
                files.transactions,
              );
            }
          }}
          title={
            busy
              ? "Wait for the current file operation to finish"
              : hasFileError
                ? "Fix the file selection errors first"
                : ready
                  ? "Read the four selected files and show a preview"
                  : "Select all four files to enable preview"
          }
          type="button"
        >
          {busy ? "Processing files…" : "Preview import"}
        </button>
        <span className="text-xs text-parchment-400">
          {totalSize > 0
            ? `${formatFileSize(totalSize)} selected · `
            : ""}
          Each file can be up to {MAX_UPLOAD_LABEL}. Original files are read in a
          streaming pass from temporary local storage and deleted afterwards.
        </span>
      </div>

      <p className="mt-3 text-xs text-parchment-400">
        Local-only: only whitelisted, parsed values are written to the private{" "}
        <code className="rounded bg-parchment-50/[0.06] px-1 py-0.5 text-parchment-300">
          data/local
        </code>{" "}
        folder. PAN, Aadhaar, contact, bank and KYC columns are ignored and never
        stored.
      </p>
    </section>
  );
}
