import Badge from "@/components/Badge";
import type {
  ReconciliationRow,
  ReconciliationStatus,
  TotalReconciliation,
} from "@/lib/types";

const statusMeta: Record<
  ReconciliationStatus,
  { label: string; tone: "blue" | "red" | "amber" | "slate" }
> = {
  matched: { label: "Matched", tone: "blue" },
  mismatch: { label: "Mismatch", tone: "red" },
  partial: { label: "Partial", tone: "amber" },
  not_available: { label: "Not available", tone: "slate" },
  no_folios: { label: "No folios", tone: "slate" },
};

function formatCurrency(value: number | null): string {
  if (value === null) return "Not available";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

export default function ReconciliationPanel({
  rows,
  total,
}: {
  rows: ReconciliationRow[];
  total: TotalReconciliation | null;
}) {
  const reviewRows = rows.filter((item) => item.status !== "matched");

  return (
    <section className="panel">
      <div className="border-b border-warm-100/15 px-5 py-4">
        <h2 className="text-base font-semibold text-parchment-100">
          Reconciliation warnings
        </h2>
        <p className="mt-1 text-xs text-parchment-400">
          Folio AUM is summed per client and compared with the client-level CURRENT
          VALUE from the Portfolio Valuation export. The client value is never
          split across folios.
        </p>
      </div>

      {reviewRows.length === 0 ? (
        <p className="px-5 py-5 text-sm text-copper-300">
          All clients with both values available reconcile within ₹1.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[850px] border-collapse text-left text-sm">
            <thead className="bg-ink-900/80 text-[11px] uppercase tracking-[0.14em] text-parchment-400">
              <tr>
                <th className="px-4 py-3 font-semibold">Client</th>
                <th className="px-4 py-3 text-right font-semibold">Folio AUM</th>
                <th className="px-4 py-3 text-right font-semibold">
                  Client current value
                </th>
                <th className="px-4 py-3 text-right font-semibold">Difference</th>
                <th className="px-4 py-3 font-semibold">Status</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-warm-100/10">
              {reviewRows.map((row) => {
                const status = statusMeta[row.status];
                return (
                  <tr key={row.client_id} className="align-top">
                    <td className="px-4 py-3">
                      <p className="font-medium text-parchment-100">{row.client_name}</p>
                      <p className="mt-1 font-mono text-[11px] text-parchment-400">
                        {row.iwell_code ?? "No code"} · {row.folio_count} folio(s)
                      </p>
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-parchment-300">
                      {formatCurrency(row.folio_aum_total)}
                      {row.folio_aum_missing_count > 0 && (
                        <p className="mt-1 text-[11px] text-amber-300">
                          {row.folio_aum_missing_count} AUM missing
                        </p>
                      )}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-parchment-300">
                      {formatCurrency(row.client_current_value)}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums text-parchment-300">
                      {formatCurrency(row.difference)}
                    </td>
                    <td className="px-4 py-3">
                      <Badge tone={status.tone}>{status.label}</Badge>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}

      {total && (
        <div className="border-t border-warm-100/15 px-5 py-4 text-xs text-parchment-400">
          <p className="font-medium text-parchment-200">Portfolio total-row check</p>
          <p className="mt-1">
            Report total {formatCurrency(total.report_total)} · sum of client rows{" "}
            {formatCurrency(total.sum_of_client_rows)} · difference{" "}
            {total.difference === null ? "—" : formatCurrency(total.difference)}{" "}
            <Badge
              tone={
                total.status === "matched"
                  ? "green"
                  : total.status === "mismatch"
                    ? "red"
                    : "slate"
              }
            >
              {total.status === "matched"
                ? "Matched"
                : total.status === "mismatch"
                  ? "Mismatch"
                  : "Not available"}
            </Badge>
          </p>
          <p className="mt-1 text-parchment-400">
            The total row is used only for this reconciliation check, never as a
            client record.
          </p>
        </div>
      )}
    </section>
  );
}
