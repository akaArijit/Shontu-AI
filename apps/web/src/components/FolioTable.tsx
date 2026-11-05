"use client";

import { useState } from "react";
import Badge from "@/components/Badge";
import FolioDetailDialog from "@/components/FolioDetailDialog";
import type { FolioRow } from "@/lib/types";

function formatCurrency(value: number | null): string {
  if (value === null) return "Not available";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatUnits(value: number | null): string {
  if (value === null) return "Not available";
  return new Intl.NumberFormat("en-IN", {
    maximumFractionDigits: 3,
  }).format(value);
}

function formatDate(value: string | null): string {
  if (!value) return "Not available";
  return new Date(`${value}T00:00:00`).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatPercent(value: number | null): string {
  if (value === null) return "Not available";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function formatDays(value: number | null): string {
  if (value === null) return "Not available";
  return `${value.toLocaleString("en-IN")} days`;
}

function MatchBadge({ status }: { status: string }) {
  if (status === "matched") return <Badge tone="blue">Matched</Badge>;
  if (status === "name_fallback") {
    return <Badge tone="amber">Name match — review</Badge>;
  }
  return <Badge tone="amber">Unmatched — needs review</Badge>;
}

function BenchmarkBadge({ status }: { status: string }) {
  if (status === "reviewed" || status === "confirmed") {
    return <Badge tone="blue">Reviewed</Badge>;
  }
  if (status === "needs_review") return <Badge tone="amber">Needs Review</Badge>;
  return <Badge tone="amber">Needs mapping</Badge>;
}

function ComparisonBadge({ status }: { status: string }) {
  if (status === "available") return <Badge tone="blue">Compared</Badge>;
  if (status === "mapping_needs_review") {
    return <Badge tone="amber">Mapping needs review</Badge>;
  }
  if (status === "mapping_missing") {
    return <Badge tone="amber">Needs mapping</Badge>;
  }
  if (status === "levels_missing") {
    return <Badge tone="amber">Levels missing</Badge>;
  }
  if (status === "no_transactions") {
    return <Badge tone="slate">No cash flows</Badge>;
  }
  if (status === "folio_return_unavailable") {
    return <Badge tone="slate">Folio return unavailable</Badge>;
  }
  if (status === "xirr_unavailable") {
    return <Badge tone="slate">Benchmark XIRR unavailable</Badge>;
  }
  return <Badge tone="slate">Not available</Badge>;
}

function comparisonMethodLabel(method: FolioRow["benchmark_comparison_method"]): string {
  if (method === "point_to_point") return "Point-to-point absolute return";
  if (method === "cash_flow_xirr") return "Same-dated cash-flow XIRR";
  return "";
}

export default function FolioTable({ rows }: { rows: FolioRow[] }) {
  const [selectedFolio, setSelectedFolio] = useState<FolioRow | null>(null);

  if (rows.length === 0) {
    return (
      <section className="panel flex flex-col items-center p-10 text-center">
        <span className="flex h-11 w-11 items-center justify-center rounded-full bg-copper-400/10 text-lg text-copper-300 ring-1 ring-inset ring-copper-400/25">
          ₹
        </span>
        <h2 className="mt-3 text-base font-semibold text-parchment-100">No folios yet</h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-parchment-400">
          Upload the four InvestWell files or load the demo data. The folio-level
          holdings and return table appears after you confirm an import.
        </p>
      </section>
    );
  }

  return (
    <>
      <section className="panel overflow-hidden">
      <div className="flex flex-col gap-1 border-b border-warm-100/15 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-parchment-100">
            Folio-level holdings and returns
          </h2>
          <p className="mt-1 text-xs text-parchment-400">
            Gross invested = purchases + SIPs + switch-ins. Net invested = gross
            invested − redemptions − switch-outs. Folio value is the AUM reported in
            Folios. Absolute return and XIRR use only dated transaction rows and are
            never estimated.
          </p>
        </div>
        <span className="shrink-0 rounded-full border border-warm-100/15 bg-parchment-50/[0.045] px-2.5 py-1 text-[11px] font-medium text-parchment-300">
          {rows.length} rows
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[3100px] border-collapse text-left text-sm">
          <thead className="border-y border-warm-100/10 bg-ink-800/85 text-[11px] uppercase tracking-[0.14em] text-parchment-400">
            <tr>
              <th className="px-4 py-3 font-semibold">Client</th>
              <th className="px-4 py-3 font-semibold">Folio</th>
              <th className="px-4 py-3 font-semibold">Scheme</th>
              <th className="px-4 py-3 font-semibold">Type</th>
              <th className="px-4 py-3 text-right font-semibold">Units</th>
              <th className="px-4 py-3 text-right font-semibold">Folio AUM</th>
              <th className="px-4 py-3 font-semibold">Valuation date</th>
              <th className="px-4 py-3 text-right font-semibold">Total invested (gross)</th>
              <th className="px-4 py-3 text-right font-semibold">Net invested</th>
              <th className="px-4 py-3 font-semibold">Holding period</th>
              <th className="px-4 py-3 text-right font-semibold">Folio abs. return</th>
              <th className="px-4 py-3 text-right font-semibold">Folio XIRR</th>
              <th className="px-4 py-3 font-semibold">Benchmark / category</th>
              <th className="px-4 py-3 text-right font-semibold">
                Benchmark return / XIRR
              </th>
              <th className="px-4 py-3 text-right font-semibold">Difference</th>
              <th className="px-4 py-3 font-semibold">Client match</th>
              <th className="px-4 py-3 font-semibold">Details</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-warm-100/10">
            {rows.map((row) => (
              <tr
                key={row.id}
                className="align-top transition-colors duration-150 hover:bg-copper-400/[0.035]"
              >
                <td className="px-4 py-4">
                  <p className="max-w-[220px] font-medium text-parchment-100">
                    {row.client_name}
                  </p>
                  <p className="mt-1 font-mono text-[11px] text-parchment-400">
                    {row.client_iwell_code ?? "No code"}
                  </p>
                </td>
                <td className="px-4 py-4 font-mono text-xs text-parchment-400">
                  {row.folio_number}
                </td>
                <td className="max-w-[270px] px-4 py-4">
                  <p className="font-medium text-parchment-200">{row.scheme_name}</p>
                  {row.notes.length > 0 && (
                    <p className="mt-1 text-[11px] text-amber-300">
                      {row.notes.join(" ")}
                    </p>
                  )}
                </td>
                <td className="px-4 py-4 text-xs text-parchment-400">{row.folio_type}</td>
                <td className="px-4 py-4 text-right tabular-nums text-parchment-300">
                  {formatUnits(row.units)}
                </td>
                <td className="px-4 py-4 text-right tabular-nums">
                  {row.aum === null ? (
                    <span className="text-xs italic text-parchment-400">
                      Not available in this file.
                    </span>
                  ) : (
                    <span className="font-medium text-parchment-100">
                      {formatCurrency(row.aum)}
                    </span>
                  )}
                </td>
                <td className="px-4 py-4 text-xs text-parchment-400">
                  {formatDate(row.value_date)}
                </td>
                <td className="px-4 py-4 text-right tabular-nums">
                  {row.gross_invested === null ? (
                    <span className="text-xs italic text-parchment-400">Not available</span>
                  ) : (
                    <span className="font-medium text-parchment-100">
                      {formatCurrency(row.gross_invested)}
                    </span>
                  )}
                  <p className="mt-1 text-[10px] text-parchment-400">
                    {row.transaction_count} transaction
                    {row.transaction_count === 1 ? "" : "s"}
                    {row.missing_date_count > 0
                      ? ` · ${row.missing_date_count} missing date`
                      : ""}
                    {row.missing_amount_count > 0
                      ? ` · ${row.missing_amount_count} missing amount`
                      : ""}
                    {row.unknown_transaction_count > 0
                      ? ` · ${row.unknown_transaction_count} unknown type`
                      : ""}
                  </p>
                </td>
                <td className="px-4 py-4 text-right tabular-nums">
                  {row.net_invested === null ? (
                    <span className="text-xs italic text-parchment-400">Not available</span>
                  ) : (
                    <span className="font-medium text-parchment-100">
                      {formatCurrency(row.net_invested)}
                    </span>
                  )}
                  {(row.redemption_proceeds ?? 0) + (row.switch_out_proceeds ?? 0) > 0 && (
                    <p className="mt-1 text-[10px] text-parchment-400">
                      {formatCurrency(
                        (row.redemption_proceeds ?? 0) + (row.switch_out_proceeds ?? 0),
                      )}{" "}
                      redeemed / switched out
                    </p>
                  )}
                </td>
                <td className="px-4 py-4 text-xs">
                  <p className="text-parchment-200">{formatDays(row.holding_period)}</p>
                  {row.first_investment_date && (
                    <p className="mt-1 text-[10px] text-parchment-400">
                      from {formatDate(row.first_investment_date)}
                    </p>
                  )}
                </td>
                <td className="px-4 py-4 text-right tabular-nums">
                  {row.absolute_return === null ? (
                    <span className="text-xs italic text-parchment-400">Not available</span>
                  ) : (
                    <span className="font-medium text-parchment-100">
                      {formatPercent(row.absolute_return)}
                    </span>
                  )}
                </td>
                <td className="px-4 py-4 text-right tabular-nums">
                  {row.xirr === null ? (
                    <span className="text-xs italic text-parchment-400">Not available</span>
                  ) : (
                    <span className="font-medium text-parchment-100">
                      {formatPercent(row.xirr)}
                    </span>
                  )}
                </td>
                <td className="max-w-[220px] px-4 py-4">
                  <p className="font-medium text-parchment-200">{row.benchmark_name}</p>
                  <BenchmarkBadge status={row.benchmark_status} />
                  {row.benchmark_comparison_method && (
                    <p className="mt-1 text-[10px] text-parchment-400">
                      {comparisonMethodLabel(row.benchmark_comparison_method)}
                    </p>
                  )}
                </td>
                <td className="max-w-[230px] px-4 py-4 text-right tabular-nums">
                  {row.benchmark_return === null ? (
                    <span className="text-xs italic text-parchment-400">Not available</span>
                  ) : (
                    <span className="font-medium text-parchment-100">
                      {formatPercent(row.benchmark_return)}
                    </span>
                  )}
                  {row.benchmark_return_type && row.benchmark_return !== null && (
                    <p className="mt-1 text-[10px] text-parchment-400">
                      {row.benchmark_return_type === "absolute"
                        ? "absolute return"
                        : "XIRR"}
                    </p>
                  )}
                  <div className="mt-1 flex justify-end">
                    <ComparisonBadge status={row.benchmark_comparison_status} />
                  </div>
                  {row.benchmark_comparison_note && (
                    <p className="mt-1 text-[10px] text-parchment-400">
                      {row.benchmark_comparison_note}
                    </p>
                  )}
                </td>
                <td className="px-4 py-4 text-right tabular-nums">
                  {row.benchmark_difference === null ? (
                    <span className="text-xs italic text-parchment-400">Not available</span>
                  ) : (
                    <>
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
                      <p
                        className={
                          row.benchmark_difference > 0
                            ? "mt-1 text-[10px] text-emerald-300"
                            : row.benchmark_difference < 0
                              ? "mt-1 text-[10px] text-rose-300"
                              : "mt-1 text-[10px] text-parchment-400"
                        }
                      >
                        {row.benchmark_difference > 0
                          ? "Folio ahead of benchmark"
                          : row.benchmark_difference < 0
                            ? "Folio behind benchmark"
                            : "In line with benchmark"}
                      </p>
                    </>
                  )}
                </td>
                <td className="px-4 py-4">
                  <MatchBadge status={row.match_status} />
                  {row.match_note && (
                    <p className="mt-1 max-w-[220px] text-[11px] text-parchment-400">
                      {row.match_note}
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
            ))}
          </tbody>
        </table>
      </div>
      </section>
      <FolioDetailDialog
        folio={selectedFolio}
        onClose={() => setSelectedFolio(null)}
      />
    </>
  );
}
