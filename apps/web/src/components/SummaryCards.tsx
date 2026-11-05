import type { DashboardSummary } from "@/lib/types";

function formatCurrency(value: number | null): string {
  if (value === null) return "Not available";
  return new Intl.NumberFormat("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 0,
  }).format(value);
}

const chipBase =
  "inline-flex items-center rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset";
const neutralChip = "bg-parchment-50/[0.05] text-parchment-300 ring-warm-100/15";
const amberChip = "bg-amber-400/10 text-amber-300 ring-amber-400/25";

export default function SummaryCards({ summary }: { summary: DashboardSummary }) {
  const cards = [
    { label: "Clients", value: summary.clients.toLocaleString("en-IN") },
    { label: "Folios", value: summary.folios.toLocaleString("en-IN") },
    {
      label: "Transactions",
      value: summary.transactions.toLocaleString("en-IN"),
      note: "dated cash flows used for folio returns",
    },
    {
      label: "Folio AUM",
      value: formatCurrency(summary.total_folio_aum),
      note: "matched clients only, as reported",
    },
    {
      label: "Client current value",
      value: formatCurrency(summary.total_current_value),
      note: "matched clients only, as reported",
    },
    {
      label: "Total invested (gross)",
      value: formatCurrency(summary.total_gross_invested),
      note: "purchases + SIPs + switch-ins",
    },
    {
      label: "Net invested",
      value: formatCurrency(summary.total_net_invested),
      note: "gross less redemptions and switch-outs",
    },
    {
      label: "XIRR available",
      value: `${summary.xirr_available.toLocaleString("en-IN")} folio(s)`,
      note: "dated cash flows plus folio AUM",
    },
  ];

  return (
    <section className="space-y-3">
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <div
            key={card.label}
            className="glass-panel relative overflow-hidden px-5 py-4"
          >
            <span
              aria-hidden
              className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-copper-400/60 via-copper-400/10 to-transparent"
            />
            <p className="eyebrow">{card.label}</p>
            <p className="mt-2 text-2xl font-semibold tracking-tight text-parchment-50">
              {card.value}
            </p>
            {card.note && <p className="mt-1 text-[11px] text-parchment-400">{card.note}</p>}
          </div>
        ))}
      </div>
      <div className="flex flex-wrap gap-2 text-xs text-parchment-400">
        <span
          className={`${chipBase} ${
            summary.needs_review > 0 ? amberChip : neutralChip
          }`}
        >
          {summary.needs_review} benchmark mappings need review
        </span>
        <span className={`${chipBase} ${neutralChip}`}>
          {summary.benchmark_reviewed} mapping(s) reviewed
        </span>
        {summary.benchmark_mapping_missing > 0 && (
          <span className={`${chipBase} ${amberChip}`}>
            {summary.benchmark_mapping_missing} folio(s) need a real benchmark mapping
          </span>
        )}
        <span
          className={`${chipBase} ${
            summary.unmatched_folios > 0 ? amberChip : neutralChip
          }`}
        >
          {summary.unmatched_folios} folio(s) unmatched
        </span>
        <span
          className={`${chipBase} ${
            summary.unmatched_portfolio_rows > 0 ? amberChip : neutralChip
          }`}
        >
          {summary.unmatched_portfolio_rows} portfolio row(s) unmatched
        </span>
        {summary.unmatched_folio_aum !== null && summary.unmatched_folio_aum > 0 && (
          <span className={`${chipBase} ${amberChip}`}>
            Unmatched folio AUM {formatCurrency(summary.unmatched_folio_aum)}
          </span>
        )}
        {summary.unmatched_current_value !== null &&
          summary.unmatched_current_value > 0 && (
            <span className={`${chipBase} ${amberChip}`}>
              Unmatched current value {formatCurrency(summary.unmatched_current_value)}
            </span>
          )}
        <span
          className={`${chipBase} ${
            summary.transactions_unmatched > 0 ? amberChip : neutralChip
          }`}
        >
          {summary.transactions_unmatched} transaction(s) unmatched
        </span>
        {summary.unknown_transactions > 0 && (
          <span className={`${chipBase} ${amberChip}`}>
            {summary.unknown_transactions} unknown transaction type(s)
          </span>
        )}
        {summary.switch_reviews > 0 && (
          <span className={`${chipBase} ${amberChip}`}>
            {summary.switch_reviews} switch leg(s) need review
          </span>
        )}
        {summary.missing_transaction_dates > 0 && (
          <span className={`${chipBase} ${amberChip}`}>
            {summary.missing_transaction_dates} transaction date(s) missing
          </span>
        )}
        {summary.missing_transaction_amounts > 0 && (
          <span className={`${chipBase} ${amberChip}`}>
            {summary.missing_transaction_amounts} transaction amount(s) missing
          </span>
        )}
        <span
          className={`${chipBase} ${
            summary.benchmark_comparisons_available > 0 ? neutralChip : amberChip
          }`}
        >
          {summary.benchmark_comparisons_available} benchmark comparison(s) available
        </span>
        {summary.benchmark_point_to_point > 0 && (
          <span className={`${chipBase} ${neutralChip}`}>
            {summary.benchmark_point_to_point} point-to-point
          </span>
        )}
        {summary.benchmark_cash_flow > 0 && (
          <span className={`${chipBase} ${neutralChip}`}>
            {summary.benchmark_cash_flow} cash-flow XIRR
          </span>
        )}
        {summary.benchmark_levels_missing > 0 && (
          <span className={`${chipBase} ${amberChip}`}>
            {summary.benchmark_levels_missing} comparison(s) missing benchmark levels
          </span>
        )}
        {summary.reconciliation_warnings > 0 && (
          <span className={`${chipBase} ${amberChip}`}>
            {summary.reconciliation_warnings} reconciliation warning(s)
          </span>
        )}
        {summary.partial_reconciliation > 0 && (
          <span className={`${chipBase} ${amberChip}`}>
            {summary.partial_reconciliation} partial reconciliation(s)
          </span>
        )}
        {summary.missing_folio_aum > 0 && (
          <span className={`${chipBase} ${amberChip}`}>
            {summary.missing_folio_aum} folio AUM value(s) missing
          </span>
        )}
        {summary.missing_current_value > 0 && (
          <span className={`${chipBase} ${amberChip}`}>
            {summary.missing_current_value} client current value(s) missing
          </span>
        )}
        <span
          className={`${chipBase} ${
            summary.issues > 0 ? amberChip : neutralChip
          }`}
        >
          {summary.issues} import issue(s)
        </span>
      </div>
    </section>
  );
}
