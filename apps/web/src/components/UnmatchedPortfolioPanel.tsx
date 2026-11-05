import Badge from "@/components/Badge";
import type { UnmatchedPortfolioRow } from "@/lib/types";

function formatCurrency(value: number | null): string {
  if (value === null) return "Not available";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

function formatPercent(value: number | null): string {
  if (value === null) return "Not available";
  return `${value > 0 ? "+" : ""}${value.toFixed(2)}%`;
}

function valueTone(value: number | null): string {
  if (value === null || value === 0) return "text-parchment-300";
  return "text-amber-300";
}

export default function UnmatchedPortfolioPanel({
  rows,
}: {
  rows: UnmatchedPortfolioRow[];
}) {
  if (rows.length === 0) return null;

  return (
    <section className="panel border-amber-400/25">
      <div className="border-b border-warm-100/15 bg-amber-400/[0.04] px-5 py-4">
        <div className="flex flex-wrap items-center gap-2">
          <h2 className="text-base font-semibold text-parchment-100">
            Unmatched portfolio rows
          </h2>
          <Badge tone="amber">Needs review</Badge>
        </div>
        <p className="mt-1 text-xs text-parchment-400">
          These Portfolio Valuation rows did not match a client in the Client
          Details workbook. They are shown for review and are not included in the
          client summary.
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[1000px] border-collapse text-left text-sm">
          <thead className="bg-ink-900/80 text-[11px] uppercase tracking-[0.14em] text-parchment-400">
            <tr>
              <th className="px-4 py-3 font-semibold">Client name in report</th>
              <th className="px-4 py-3 font-semibold">IWELL code</th>
              <th className="px-4 py-3 text-right font-semibold">Current value</th>
              <th className="px-4 py-3 text-right font-semibold">Purchase value</th>
              <th className="px-4 py-3 text-right font-semibold">Gain</th>
              <th className="px-4 py-3 text-right font-semibold">Abs. return</th>
              <th className="px-4 py-3 text-right font-semibold">CAGR</th>
              <th className="px-4 py-3 font-semibold">Reason</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-warm-100/10">
            {rows.map((row) => (
              <tr
                key={row.id}
                className="align-top transition-colors hover:bg-parchment-50/[0.035]"
              >
                <td className="px-4 py-3 font-medium text-parchment-100">
                  {row.client_name}
                </td>
                <td className="px-4 py-3 font-mono text-xs text-parchment-400">
                  {row.source_iwell_code ?? "Not available"}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-parchment-200">
                  {formatCurrency(row.current_value)}
                </td>
                <td className="px-4 py-3 text-right tabular-nums text-parchment-300">
                  {formatCurrency(row.purchase_value)}
                </td>
                <td
                  className={`px-4 py-3 text-right tabular-nums ${valueTone(row.gain)}`}
                >
                  {formatCurrency(row.gain)}
                </td>
                <td
                  className={`px-4 py-3 text-right tabular-nums ${valueTone(
                    row.absolute_return,
                  )}`}
                >
                  {formatPercent(row.absolute_return)}
                </td>
                <td
                  className={`px-4 py-3 text-right tabular-nums ${valueTone(row.cagr)}`}
                >
                  {formatPercent(row.cagr)}
                </td>
                <td className="px-4 py-3 text-xs text-amber-200">
                  {row.match_note ?? "No matching client."}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
