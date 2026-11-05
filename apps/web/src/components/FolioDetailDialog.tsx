"use client";

import { useEffect } from "react";
import Badge from "@/components/Badge";
import {
  formatCurrency,
  formatDate,
  formatDays,
  formatPercent,
} from "@/lib/format";
import type { FolioDetail } from "@/lib/types";

function comparisonDetail(folio: FolioDetail) {
  if (folio.benchmark_comparison_status === "available") {
    if (folio.benchmark_difference === null) {
      return { tone: "slate" as const, label: "Not available" };
    }
    if (folio.benchmark_difference > 0) {
      return { tone: "green" as const, label: "Ahead of benchmark" };
    }
    if (folio.benchmark_difference < 0) {
      return { tone: "red" as const, label: "Behind benchmark" };
    }
    return { tone: "slate" as const, label: "In line with benchmark" };
  }
  if (
    folio.benchmark_comparison_status === "mapping_missing" ||
    folio.benchmark_comparison_status === "mapping_needs_review"
  ) {
    return { tone: "amber" as const, label: "Needs review" };
  }
  if (folio.benchmark_comparison_status === "levels_missing") {
    return { tone: "amber" as const, label: "Levels missing" };
  }
  return { tone: "slate" as const, label: "Not available" };
}

function comparisonMethodLabel(folio: FolioDetail): string {
  if (folio.benchmark_comparison_method === "point_to_point") {
    return "Point-to-point absolute return";
  }
  if (folio.benchmark_comparison_method === "cash_flow_xirr") {
    return "Same-dated cash-flow XIRR";
  }
  return "Not available";
}

function benchmarkReturnLabel(folio: FolioDetail): string {
  if (folio.benchmark_return_type === "absolute") return "Benchmark return";
  if (folio.benchmark_return_type === "xirr") return "Benchmark XIRR";
  return "Benchmark return / XIRR";
}

function plainEnglishStatus(folio: FolioDetail) {
  if (folio.aum === null) {
    return {
      tone: "slate" as const,
      text: "Folio current value is missing.",
    };
  }
  if (folio.benchmark_comparison_status === "mapping_missing") {
    return {
      tone: "amber" as const,
      text: "Needs review: no benchmark mapping is saved for this scheme.",
    };
  }
  if (folio.benchmark_comparison_status === "mapping_needs_review") {
    return {
      tone: "amber" as const,
      text: "Needs review: the benchmark mapping is automatic and has not been approved.",
    };
  }
  if (folio.benchmark_comparison_status === "levels_missing") {
    const count = folio.benchmark_missing_date_count ?? 0;
    return {
      tone: "amber" as const,
      text:
        count > 0
          ? `Not available: ${count.toLocaleString("en-IN")} local benchmark date(s) are missing. Missing levels are never estimated.`
          : "Not available: local benchmark levels are missing for this comparison.",
    };
  }
  if (folio.benchmark_comparison_status === "no_transactions") {
    return {
      tone: "slate" as const,
      text: "Not available: this folio has no dated transaction cash flows.",
    };
  }
  if (
    folio.benchmark_comparison_status === "xirr_unavailable" ||
    folio.benchmark_comparison_status === "folio_return_unavailable"
  ) {
    return {
      tone: "slate" as const,
      text: "Not available: a return could not be calculated from the available dates and values.",
    };
  }
  if (
    folio.benchmark_comparison_status === "available" &&
    folio.benchmark_difference !== null
  ) {
    const difference = Math.abs(folio.benchmark_difference).toFixed(2);
    if (folio.benchmark_difference > 0) {
      return {
        tone: "green" as const,
        text: `Folio is ahead of benchmark by ${difference}%.`,
      };
    }
    if (folio.benchmark_difference < 0) {
      return {
        tone: "red" as const,
        text: `Folio is behind benchmark by ${difference}%.`,
      };
    }
    return {
      tone: "slate" as const,
      text: "Folio is in line with benchmark.",
    };
  }
  return {
    tone: "slate" as const,
    text: "Benchmark comparison is not available for this folio.",
  };
}

const plainStatusClasses = {
  green: "border-emerald-400/20 bg-emerald-400/[0.06] text-emerald-200",
  red: "border-rose-400/20 bg-rose-400/[0.06] text-rose-200",
  amber: "border-amber-400/20 bg-amber-400/[0.06] text-amber-200",
  slate: "border-warm-100/15 bg-parchment-50/[0.035] text-parchment-300",
};

function DetailItem({
  label,
  value,
  valueClass = "text-parchment-100",
  note,
}: {
  label: string;
  value: string;
  valueClass?: string;
  note?: string;
}) {
  return (
    <div className="min-w-0 rounded-xl border border-warm-100/15 bg-parchment-50/[0.03] px-3.5 py-3">
      <p className="eyebrow">{label}</p>
      <p className={`mt-1 break-words text-sm font-medium tabular-nums ${valueClass}`}>
        {value}
      </p>
      {note && <p className="mt-1 text-[11px] text-parchment-400">{note}</p>}
    </div>
  );
}

export default function FolioDetailDialog({
  folio,
  onClose,
}: {
  folio: FolioDetail | null;
  onClose: () => void;
}) {
  useEffect(() => {
    if (!folio) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [folio, onClose]);

  if (!folio) return null;

  const status = comparisonDetail(folio);
  const plainStatus = plainEnglishStatus(folio);
  const differenceTone =
    folio.benchmark_comparison_status === "available" &&
    folio.benchmark_difference !== null
      ? folio.benchmark_difference > 0
        ? "text-emerald-300"
        : folio.benchmark_difference < 0
          ? "text-rose-300"
          : "text-parchment-200"
      : "text-parchment-300";

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-[#0b0908]/85 p-4 backdrop-blur-sm"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
      role="presentation"
    >
      <div
        aria-labelledby="folio-detail-title"
        aria-modal="true"
        className="glass-dialog max-h-[90vh] w-full max-w-3xl overflow-y-auto p-5 sm:p-6"
        role="dialog"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="eyebrow">Folio detail</p>
              <Badge tone={status.tone}>{status.label}</Badge>
            </div>
            <h2
              className="mt-2 text-xl font-semibold tracking-tight text-parchment-50"
              id="folio-detail-title"
            >
              {folio.client_name}
            </h2>
            <p className="mt-1 font-mono text-xs text-copper-300">
              {folio.folio_number}
            </p>
            <p className="mt-2 max-w-xl text-sm leading-6 text-parchment-300">
              {folio.scheme_name}
            </p>
          </div>
          <button
            aria-label="Close folio detail"
            className="btn-secondary shrink-0 px-3 py-1.5 text-xs"
            onClick={onClose}
            type="button"
          >
            Close
          </button>
        </div>

        <div
          className={`mt-5 rounded-xl border px-4 py-3 text-sm leading-6 ${plainStatusClasses[plainStatus.tone]}`}
        >
          {plainStatus.text}
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          <DetailItem label="Client name" value={folio.client_name} />
          <DetailItem label="Folio number" value={folio.folio_number} />
          <DetailItem label="Benchmark" value={folio.benchmark_name} />
          <DetailItem label="Scheme" value={folio.scheme_name} />
          <DetailItem
            label="Invested amount"
            value={formatCurrency(
              folio.gross_invested ?? folio.invested_amount,
            )}
            note="Gross purchases + SIPs + switch-ins"
          />
          <DetailItem
            label="Current value"
            value={
              folio.aum === null
                ? "Not available in this file."
                : formatCurrency(folio.aum)
            }
            valueClass={
              folio.aum === null ? "italic text-parchment-400" : "text-parchment-100"
            }
          />
          <DetailItem
            label="Holding period"
            value={formatDays(folio.holding_period)}
            note={
              folio.first_investment_date
                ? `From ${formatDate(folio.first_investment_date)}`
                : undefined
            }
          />
          <DetailItem
            label="Absolute return"
            value={formatPercent(folio.absolute_return)}
            valueClass={
              folio.absolute_return === null
                ? "italic text-parchment-400"
                : "text-parchment-100"
            }
          />
          <DetailItem
            label="XIRR"
            value={formatPercent(folio.xirr)}
            valueClass={
              folio.xirr === null ? "italic text-parchment-400" : "text-parchment-100"
            }
          />
          <DetailItem
            label={benchmarkReturnLabel(folio)}
            value={formatPercent(folio.benchmark_return)}
            valueClass={
              folio.benchmark_return === null
                ? "italic text-parchment-400"
                : "text-parchment-100"
            }
          />
          <DetailItem
            label="Difference"
            value={formatPercent(folio.benchmark_difference)}
            valueClass={`${differenceTone} font-semibold`}
            note={
              folio.benchmark_difference === null
                ? "Comparison is not available."
                : `${status.label}.`
            }
          />
          <DetailItem
            label="Comparison method"
            value={comparisonMethodLabel(folio)}
            valueClass="text-parchment-200"
          />
        </div>

        {folio.benchmark_comparison_note && (
          <div className="mt-4 rounded-xl border border-amber-400/20 bg-amber-400/[0.06] px-4 py-3 text-xs leading-5 text-amber-200">
            {folio.benchmark_comparison_note}
          </div>
        )}

        {(folio.benchmark_missing_date_count ?? 0) > 0 ? (
          <div className="mt-3 rounded-xl border border-rose-400/20 bg-rose-400/[0.05] px-4 py-3 text-xs leading-5 text-rose-200">
            <p className="font-semibold">
              {folio.benchmark_missing_date_count?.toLocaleString("en-IN")} missing
              benchmark date(s)
            </p>
            <p className="mt-1">
              {(folio.benchmark_missing_dates ?? []).map(formatDate).join(", ")}
              {(folio.benchmark_missing_date_count ?? 0) >
              (folio.benchmark_missing_dates ?? []).length
                ? ` … ${(folio.benchmark_missing_date_count ?? 0) - (folio.benchmark_missing_dates ?? []).length} more. See Benchmark Data for the full exact list.`
                : "."}
            </p>
            <p className="mt-1 text-rose-200/80">
              The comparison stays Not available. Missing levels are not
              interpolated or estimated.
            </p>
          </div>
        ) : null}

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-warm-100/15 pt-4 text-[11px] text-parchment-400">
          <span>
            Benchmark mapping status:{" "}
            <strong className="font-medium text-parchment-300">
              {folio.benchmark_status}
            </strong>
          </span>
          <span>Values are reported or calculated from the local snapshot.</span>
        </div>
      </div>
    </div>
  );
}
