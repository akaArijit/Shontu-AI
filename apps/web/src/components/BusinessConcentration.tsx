import type { ReactNode } from "react";
import { formatCurrency } from "@/lib/format";
import type { BusinessReviewResponse } from "@/lib/types";

type Concentration = BusinessReviewResponse["concentration"];
type BarItem = {
  name: string;
  value: number;
  share: number;
  folio_count?: number;
};

function BarList({
  items,
  limit,
  emptyText,
}: {
  items: BarItem[];
  limit?: number;
  emptyText: string;
}) {
  const visible = typeof limit === "number" ? items.slice(0, limit) : items;
  const maxValue = Math.max(...visible.map((item) => item.value), 0);

  if (visible.length === 0) {
    return <p className="px-4 py-6 text-sm text-parchment-400">{emptyText}</p>;
  }

  return (
    <ol className="space-y-3 px-4 py-4">
      {visible.map((item) => {
        const width = maxValue > 0 ? (item.value / maxValue) * 100 : 0;
        return (
          <li key={item.name}>
            <div className="flex items-start justify-between gap-3 text-xs">
              <div className="min-w-0">
                <p className="truncate font-medium text-parchment-200" title={item.name}>
                  {item.name}
                </p>
                <p className="mt-0.5 text-[10px] text-parchment-400">
                  {formatCurrency(item.value)}
                  {typeof item.folio_count === "number"
                    ? ` · ${item.folio_count} folio${item.folio_count === 1 ? "" : "s"}`
                    : ""}
                </p>
              </div>
              <span className="shrink-0 tabular-nums text-[10px] text-parchment-400">
                {item.share.toFixed(1)}%
              </span>
            </div>
            <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-parchment-50/[0.06]">
              <div
                className="h-full rounded-full bg-copper-400/70"
                style={{ width: `${Math.max(2, width)}%` }}
              />
            </div>
          </li>
        );
      })}
    </ol>
  );
}

function ConcentrationPanel({
  title,
  note,
  children,
  count,
}: {
  title: string;
  note: string;
  children: ReactNode;
  count?: string;
}) {
  return (
    <section className="panel-inset overflow-hidden">
      <div className="border-b border-warm-100/15 px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <h3 className="text-sm font-semibold text-parchment-100">{title}</h3>
          {count && (
            <span className="shrink-0 rounded-full border border-warm-100/15 bg-parchment-50/[0.045] px-2 py-0.5 text-[10px] font-medium text-parchment-300">
              {count}
            </span>
          )}
        </div>
        <p className="mt-1 text-[11px] leading-4 text-parchment-400">{note}</p>
      </div>
      {children}
    </section>
  );
}

export default function BusinessConcentration({
  data,
}: {
  data: Concentration;
}) {
  return (
    <section>
      <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-base font-semibold text-parchment-100">
            Business concentration
          </h2>
          <p className="mt-1 text-xs leading-5 text-parchment-400">
            Where the book is concentrated. Benchmark and scheme bars use folio
            AUM; client bars use the Portfolio Valuation CURRENT VALUE exactly as
            reported.
          </p>
        </div>
        <span className="text-[11px] text-parchment-400">
          Folio AUM total {formatCurrency(data.total_folio_value)}
        </span>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <ConcentrationPanel
          count={`${data.by_benchmark.length} categories`}
          note="Current value grouped by benchmark / category."
          title="By benchmark / category"
        >
          <BarList
            emptyText="No folio current value is available yet."
            items={data.by_benchmark}
          />
        </ConcentrationPanel>

        <ConcentrationPanel
          count={`Top ${Math.min(8, data.top_clients.length)} of ${data.top_clients.length}`}
          note="Clients ranked by reported current value."
          title="Top clients"
        >
          <BarList
            emptyText="No client current value is available yet."
            items={data.top_clients}
            limit={8}
          />
        </ConcentrationPanel>

        <ConcentrationPanel
          count={`Top ${Math.min(8, data.top_schemes.length)} of ${data.top_schemes.length}`}
          note="Schemes ranked by folio current value (AUM)."
          title="Top schemes"
        >
          <BarList
            emptyText="No folio current value is available yet."
            items={data.top_schemes}
            limit={8}
          />
        </ConcentrationPanel>
      </div>

      {(data.missing_folio_value_folios > 0 ||
        data.clients_without_current_value > 0) && (
        <p className="mt-2 text-[11px] leading-5 text-parchment-400">
          {data.missing_folio_value_folios > 0
            ? `${data.missing_folio_value_folios} folio(s) have no current value and are excluded from folio-based bars.`
            : ""}{" "}
          {data.clients_without_current_value > 0
            ? `${data.clients_without_current_value} client(s) have no reported current value and are excluded from client bars.`
            : ""}
        </p>
      )}
    </section>
  );
}
