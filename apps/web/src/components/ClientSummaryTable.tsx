import Badge from "@/components/Badge";
import type { ClientSummary, ReconciliationStatus } from "@/lib/types";

const statusMeta: Record<
  ReconciliationStatus,
  { label: string; tone: "blue" | "red" | "amber" | "slate" }
> = {
  matched: { label: "Matched", tone: "blue" },
  mismatch: { label: "Mismatch — review", tone: "red" },
  partial: { label: "Partial — some AUM missing", tone: "amber" },
  not_available: { label: "Not available", tone: "slate" },
  no_folios: { label: "No folios imported", tone: "slate" },
};

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

function formatDays(value: number | null): string {
  if (value === null) return "Not available";
  return `${value.toLocaleString("en-IN")} days`;
}

function valueTone(value: number | null): string {
  if (value === null || value === 0) return "text-parchment-300";
  return value > 0 ? "text-emerald-300" : "text-rose-300";
}

export default function ClientSummaryTable({ rows }: { rows: ClientSummary[] }) {
  if (rows.length === 0) {
    return (
      <section className="panel flex flex-col items-center p-10 text-center">
        <span className="flex h-11 w-11 items-center justify-center rounded-full bg-copper-400/10 text-lg text-copper-300 ring-1 ring-inset ring-copper-400/25">
          ◎
        </span>
        <h2 className="mt-3 text-base font-semibold text-parchment-100">
          No client snapshot yet
        </h2>
        <p className="mx-auto mt-2 max-w-md text-sm leading-6 text-parchment-400">
          Upload the four InvestWell files or load the demo data. The
          client-level summary appears after you confirm an import.
        </p>
      </section>
    );
  }

  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-col gap-1 border-b border-warm-100/15 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-parchment-100">
            Client-level portfolio summary
          </h2>
          <p className="mt-1 text-xs text-parchment-400">
            Current value, gain, absolute return and CAGR are exactly as reported by
            InvestWell. Folio AUM is the sum of the Folios export and is not allocated
            across schemes.
          </p>
        </div>
        <span className="shrink-0 rounded-full border border-warm-100/15 bg-parchment-50/[0.045] px-2.5 py-1 text-[11px] font-medium text-parchment-300">
          {rows.length} clients
        </span>
      </div>

      <div className="overflow-x-auto">
        <table className="w-full min-w-[1500px] border-collapse text-left text-sm">
          <thead className="border-y border-warm-100/10 bg-ink-800/85 text-[11px] uppercase tracking-[0.14em] text-parchment-400">
            <tr>
              <th className="px-4 py-3 font-semibold">Client</th>
              <th className="px-4 py-3 font-semibold">IWELL code</th>
              <th className="px-4 py-3 text-right font-semibold">Folios</th>
              <th className="px-4 py-3 text-right font-semibold">Folio AUM</th>
              <th className="px-4 py-3 text-right font-semibold">Current value</th>
              <th className="px-4 py-3 text-right font-semibold">Purchase value</th>
              <th className="px-4 py-3 text-right font-semibold">Gain</th>
              <th className="px-4 py-3 text-right font-semibold">Abs. return</th>
              <th className="px-4 py-3 text-right font-semibold">CAGR</th>
              <th className="px-4 py-3 text-right font-semibold">Avg. holding</th>
              <th className="px-4 py-3 font-semibold">Reconciliation</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-warm-100/10">
            {rows.map((row) => {
              const status = statusMeta[row.reconciliation_status];
              return (
                <tr
                  key={row.id}
                  className="align-top transition-colors duration-150 hover:bg-copper-400/[0.035]"
                >
                  <td className="px-4 py-4">
                    <p className="font-medium text-parchment-100">{row.name}</p>
                    {row.notes.length > 0 && (
                      <p className="mt-1 max-w-[260px] text-[11px] text-amber-300">
                        {row.notes[0]}
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-4 font-mono text-xs text-parchment-400">
                    {row.iwell_code ?? "Not available"}
                  </td>
                  <td className="px-4 py-4 text-right tabular-nums text-parchment-300">
                    {row.folio_count}
                  </td>
                  <td className="px-4 py-4 text-right tabular-nums text-parchment-200">
                    {formatCurrency(row.folio_aum_total)}
                    {row.folio_aum_missing_count > 0 && (
                      <p className="mt-1 text-[11px] text-amber-300">
                        {row.folio_aum_missing_count} missing
                      </p>
                    )}
                  </td>
                  <td className="px-4 py-4 text-right tabular-nums text-parchment-100">
                    {formatCurrency(row.current_value)}
                  </td>
                  <td className="px-4 py-4 text-right tabular-nums text-parchment-300">
                    {formatCurrency(row.purchase_value)}
                  </td>
                  <td
                    className={`px-4 py-4 text-right tabular-nums ${valueTone(row.gain)}`}
                  >
                    {formatCurrency(row.gain)}
                  </td>
                  <td className="px-4 py-4 text-right tabular-nums">
                    <span className={`font-medium ${valueTone(row.absolute_return)}`}>
                      {formatPercent(row.absolute_return)}
                    </span>
                    {row.absolute_return !== null && (
                      <p className="mt-1 text-[10px] text-parchment-400">as reported</p>
                    )}
                  </td>
                  <td className="px-4 py-4 text-right tabular-nums">
                    <span className={`font-medium ${valueTone(row.cagr)}`}>
                      {formatPercent(row.cagr)}
                    </span>
                    {row.cagr !== null && (
                      <p className="mt-1 text-[10px] text-parchment-400">as reported</p>
                    )}
                  </td>
                  <td className="px-4 py-4 text-right tabular-nums text-parchment-300">
                    {formatDays(row.avg_holding_days)}
                  </td>
                  <td className="px-4 py-4">
                    <Badge tone={status.tone}>{status.label}</Badge>
                    {row.difference !== null && (
                      <p className="mt-1.5 text-[11px] text-parchment-400">
                        Folio AUM − client value: {formatCurrency(row.difference)}
                      </p>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="border-t border-warm-100/15 px-5 py-3 text-[11px] text-parchment-400">
        “Folio AUM − client value” is shown only for review. The app does not
        allocate the client-level current value across folios.
      </p>
    </section>
  );
}
