"use client";

import { useState } from "react";
import Badge from "@/components/Badge";
import FolioDetailDialog from "@/components/FolioDetailDialog";
import { formatCurrency, formatPercent } from "@/lib/format";
import { performanceMeta } from "@/lib/review";
import type { BusinessReviewFolio } from "@/lib/types";

function benchmarkReturnLabel(row: BusinessReviewFolio): string {
  if (row.benchmark_return_type === "absolute") return "absolute return";
  if (row.benchmark_return_type === "xirr") return "XIRR";
  return "return / XIRR";
}

function statusNote(row: BusinessReviewFolio): string | null {
  if (row.performance === "needs_review") {
    return "Mapping or levels need review";
  }
  if (row.performance === "not_available") {
    return row.benchmark_comparison_note ?? "Comparison not available";
  }
  return null;
}

export default function BusinessReviewTable({
  rows,
  onClearFilters,
}: {
  rows: BusinessReviewFolio[];
  onClearFilters: () => void;
}) {
  const [selectedFolio, setSelectedFolio] =
    useState<BusinessReviewFolio | null>(null);

  if (rows.length === 0) {
    return (
      <div className="flex flex-col items-center px-5 py-12 text-center">
        <span className="flex h-11 w-11 items-center justify-center rounded-full bg-copper-400/10 text-lg text-copper-300 ring-1 ring-inset ring-copper-400/25">
          ⌕
        </span>
        <h3 className="mt-3 text-base font-semibold text-parchment-100">
          No folios match these filters
        </h3>
        <p className="mt-2 max-w-md text-sm leading-6 text-parchment-400">
          Clear the filters to see the full folio list, or raise the minimum
          current value threshold.
        </p>
        <button
          className="btn-secondary mt-4 px-3 py-1.5 text-xs"
          onClick={onClearFilters}
          type="button"
        >
          Clear filters
        </button>
      </div>
    );
  }

  return (
    <>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1500px] border-collapse text-left text-sm">
          <thead className="border-y border-warm-100/10 bg-ink-800/85 text-[11px] uppercase tracking-[0.14em] text-parchment-400">
            <tr>
              <th className="px-4 py-3 font-semibold">Client / folio</th>
              <th className="px-4 py-3 font-semibold">Scheme</th>
              <th className="px-4 py-3 font-semibold">Benchmark</th>
              <th className="px-4 py-3 text-right font-semibold">
                Current value
              </th>
              <th className="px-4 py-3 text-right font-semibold">
                Folio return / XIRR
              </th>
              <th className="px-4 py-3 text-right font-semibold">
                Benchmark return / XIRR
              </th>
              <th className="px-4 py-3 text-right font-semibold">Difference</th>
              <th className="px-4 py-3 font-semibold">Status</th>
              <th className="px-4 py-3 font-semibold">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-warm-100/10">
            {rows.map((row) => {
              const meta = performanceMeta[row.performance];
              const note = statusNote(row);
              return (
                <tr
                  key={row.id}
                  className="align-top transition-colors duration-150 hover:bg-copper-400/[0.035]"
                >
                  <td className="px-4 py-4">
                    <p className="max-w-[220px] font-medium text-parchment-100">
                      {row.client_name}
                    </p>
                    <p className="mt-1 font-mono text-[11px] text-parchment-400">
                      {row.folio_number}
                    </p>
                  </td>
                  <td className="max-w-[260px] px-4 py-4">
                    <p className="font-medium text-parchment-200">
                      {row.scheme_name}
                    </p>
                  </td>
                  <td className="max-w-[220px] px-4 py-4">
                    <p className="font-medium text-parchment-200">
                      {row.benchmark_name}
                    </p>
                    <p className="mt-1 text-[10px] text-parchment-400">
                      {row.benchmark_status === "reviewed"
                        ? "Review complete"
                        : "Mapping review required"}
                    </p>
                  </td>
                  <td className="px-4 py-4 text-right tabular-nums">
                    {row.aum === null ? (
                      <span className="text-xs italic text-parchment-400">
                        Not available
                      </span>
                    ) : (
                      <span className="font-medium text-parchment-100">
                        {formatCurrency(row.aum)}
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-4 text-right tabular-nums">
                    <p className="font-medium text-parchment-100">
                      {formatPercent(row.absolute_return)}
                    </p>
                    <p className="mt-1 text-[10px] text-parchment-400">
                      XIRR {formatPercent(row.xirr)}
                    </p>
                  </td>
                  <td className="px-4 py-4 text-right tabular-nums">
                    <p className="font-medium text-parchment-100">
                      {formatPercent(row.benchmark_return)}
                    </p>
                    <p className="mt-1 text-[10px] text-parchment-400">
                      {benchmarkReturnLabel(row)}
                    </p>
                  </td>
                  <td className="px-4 py-4 text-right tabular-nums">
                    {row.benchmark_difference === null ? (
                      <span className="text-xs italic text-parchment-400">
                        Not available
                      </span>
                    ) : (
                      <span
                        className={
                          row.benchmark_difference > 0
                            ? "font-semibold text-emerald-300"
                            : row.benchmark_difference < 0
                              ? "font-semibold text-rose-300"
                              : "font-semibold text-parchment-200"
                        }
                      >
                        {formatPercent(row.benchmark_difference)}
                      </span>
                    )}
                  </td>
                  <td className="max-w-[220px] px-4 py-4">
                    <Badge tone={meta.tone}>{meta.label}</Badge>
                    {note && (
                      <p className="mt-1.5 text-[10px] leading-4 text-parchment-400">
                        {note}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-4">
                    <button
                      aria-label={`View details for ${row.client_name}, folio ${row.folio_number}`}
                      className="btn-secondary whitespace-nowrap px-3 py-1.5 text-xs"
                      onClick={() => setSelectedFolio(row)}
                      title="Open the shared folio detail popup"
                      type="button"
                    >
                      View
                    </button>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <FolioDetailDialog
        folio={selectedFolio}
        onClose={() => setSelectedFolio(null)}
      />
    </>
  );
}
