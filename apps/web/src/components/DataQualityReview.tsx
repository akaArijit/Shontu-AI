"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import Badge from "@/components/Badge";
import { formatCurrency } from "@/lib/format";
import { performanceMeta } from "@/lib/review";
import type {
  BusinessReviewResponse,
  QualityFolioItem,
  ReconciliationRow,
  UnmatchedPortfolioRow,
} from "@/lib/types";

type DataQuality = BusinessReviewResponse["data_quality"];

function QualityCard({
  title,
  count,
  description,
  items,
  emptyText,
}: {
  title: string;
  count: number;
  description: string;
  items: ReactNode[];
  emptyText: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? items : items.slice(0, 4);

  return (
    <section className="panel-inset flex flex-col p-4">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-parchment-100">{title}</h3>
          <p className="mt-1 text-[11px] leading-5 text-parchment-400">
            {description}
          </p>
        </div>
        <Badge tone={count > 0 ? "amber" : "slate"}>{count}</Badge>
      </div>

      {count === 0 ? (
        <p className="mt-3 rounded-lg border border-warm-100/10 bg-parchment-50/[0.025] px-3 py-2 text-xs text-parchment-400">
          {emptyText}
        </p>
      ) : (
        <ul className="mt-3 space-y-2">
          {visible.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      )}

      {items.length > 4 && (
        <button
          className="mt-3 self-start text-[11px] font-medium text-copper-300 hover:text-copper-200"
          onClick={() => setExpanded((value) => !value)}
          type="button"
        >
          {expanded ? "Show fewer" : `Show all ${items.length}`}
        </button>
      )}
    </section>
  );
}

function FolioQualityLine({ item }: { item: QualityFolioItem }) {
  const meta = performanceMeta[item.performance];
  return (
    <div className="rounded-lg border border-warm-100/10 bg-parchment-50/[0.025] px-3 py-2">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
        <p className="text-xs font-medium text-parchment-200">
          {item.client_name}
        </p>
        <span className="font-mono text-[10px] text-parchment-400">
          {item.folio_number}
        </span>
        <Badge tone={meta.tone}>{meta.label}</Badge>
      </div>
      <p className="mt-1 truncate text-[11px] text-parchment-400" title={item.scheme_name}>
        {item.scheme_name}
      </p>
      <p className="mt-1 text-[10px] leading-4 text-parchment-400">{item.note}</p>
    </div>
  );
}

function UnmatchedPortfolioLine({ item }: { item: UnmatchedPortfolioRow }) {
  return (
    <div className="rounded-lg border border-warm-100/10 bg-parchment-50/[0.025] px-3 py-2">
      <p className="text-xs font-medium text-parchment-200">{item.client_name}</p>
      <p className="mt-1 font-mono text-[10px] text-parchment-400">
        {item.source_iwell_code ?? "No code"}
      </p>
      <p className="mt-1 text-[10px] text-parchment-400">
        Current value {formatCurrency(item.current_value)}
      </p>
      {item.match_note && (
        <p className="mt-1 text-[10px] leading-4 text-parchment-400">
          {item.match_note}
        </p>
      )}
    </div>
  );
}

function reconciliationLabel(status: string): string {
  if (status === "mismatch") return "Mismatch";
  if (status === "partial") return "Partial";
  if (status === "not_available") return "Not available";
  if (status === "no_folios") return "No folios";
  return "Review";
}

function ReconciliationLine({ item }: { item: ReconciliationRow }) {
  return (
    <div className="rounded-lg border border-warm-100/10 bg-parchment-50/[0.025] px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-xs font-medium text-parchment-200">{item.client_name}</p>
        <Badge tone={item.status === "matched" ? "blue" : "amber"}>
          {reconciliationLabel(item.status)}
        </Badge>
      </div>
      <p className="mt-1 text-[10px] text-parchment-400">
        Folio AUM {formatCurrency(item.folio_aum_total)} · client value{" "}
        {formatCurrency(item.client_current_value)}
        {item.difference !== null
          ? ` · difference ${formatCurrency(item.difference)}`
          : ""}
      </p>
      {item.folio_aum_missing_count > 0 && (
        <p className="mt-1 text-[10px] text-amber-300">
          {item.folio_aum_missing_count} folio AUM value missing
        </p>
      )}
    </div>
  );
}

function TransactionIssueLine({
  item,
}: {
  item: DataQuality["transaction_issues"][number];
}) {
  return (
    <div className="rounded-lg border border-warm-100/10 bg-parchment-50/[0.025] px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <p className="text-xs font-medium text-parchment-200">
          {item.client_name}
        </p>
        <span className="font-mono text-[10px] text-parchment-400">
          {item.folio_number}
        </span>
      </div>
      <p className="mt-1 truncate text-[11px] text-parchment-400">
        {item.scheme_name}
      </p>
      <p className="mt-1 text-[10px] text-amber-300">{item.summary}</p>
    </div>
  );
}

export default function DataQualityReview({
  data,
}: {
  data: DataQuality;
}) {
  return (
    <section className="panel overflow-hidden">
      <div className="flex flex-col gap-3 border-b border-warm-100/15 px-5 py-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <h2 className="text-base font-semibold text-parchment-100">
              Data-quality review
            </h2>
            <Badge tone={data.total_items > 0 ? "amber" : "slate"}>
              {data.total_items} item{data.total_items === 1 ? "" : "s"}
            </Badge>
          </div>
          <p className="mt-1 max-w-3xl text-xs leading-5 text-parchment-400">
            Missing values, mapping gaps, levels gaps, unmatched rows and
            reconciliation warnings. Items are never repaired or estimated; fix
            the source or review the mapping locally.
          </p>
        </div>
        <Link
          className="btn-secondary shrink-0 px-3 py-1.5 text-xs"
          href="/benchmarks"
        >
          Review mappings &amp; levels
        </Link>
      </div>

      <div className="grid gap-3 p-4 md:grid-cols-2">
        <QualityCard
          count={data.counts.missing_current_value}
          description="Folios where the Folios export has no AUM / current value."
          emptyText="Every folio has a reported current value."
          items={data.missing_current_value.map((item) => (
            <FolioQualityLine item={item} key={item.folio_id} />
          ))}
          title="Missing current value"
        />
        <QualityCard
          count={data.counts.missing_benchmark_mapping}
          description="Schemes with no usable benchmark mapping."
          emptyText="No folio is missing its benchmark mapping."
          items={data.missing_benchmark_mapping.map((item) => (
            <FolioQualityLine item={item} key={item.folio_id} />
          ))}
          title="Missing benchmark mapping"
        />
        <QualityCard
          count={data.counts.mapping_needs_review}
          description="Automatic mappings waiting for local approval."
          emptyText="No automatic mapping is waiting for review."
          items={data.mapping_needs_review.map((item) => (
            <FolioQualityLine item={item} key={item.folio_id} />
          ))}
          title="Mapping needs review"
        />
        <QualityCard
          count={data.counts.missing_benchmark_levels}
          description="Required closing levels are missing for the folio dates."
          emptyText="No mapped folio is waiting for benchmark levels."
          items={data.missing_benchmark_levels.map((item) => (
            <FolioQualityLine item={item} key={item.folio_id} />
          ))}
          title="Missing benchmark levels"
        />
        <QualityCard
          count={data.counts.unmatched_folios}
          description="Folio rows whose client could not be matched."
          emptyText="Every folio is matched to a client."
          items={data.unmatched_folios.map((item) => (
            <FolioQualityLine item={item} key={item.folio_id} />
          ))}
          title="Unmatched folios"
        />
        <QualityCard
          count={data.counts.unmatched_portfolio_rows}
          description="Portfolio Valuation rows without a matching client."
          emptyText="Every portfolio row is matched."
          items={data.unmatched_portfolio.map((item) => (
            <UnmatchedPortfolioLine item={item} key={item.id} />
          ))}
          title="Unmatched portfolio rows"
        />
        <QualityCard
          count={data.counts.reconciliation_warnings}
          description="Client-level totals that need a manual check."
          emptyText="All clients reconcile within ₹1."
          items={data.reconciliation_warnings.map((item) => (
            <ReconciliationLine item={item} key={item.client_id} />
          ))}
          title="Reconciliation warnings"
        />
        <QualityCard
          count={data.counts.transaction_issues}
          description="Folios with unknown transaction types or missing dates/amounts."
          emptyText="No transaction issue was found in matched folios."
          items={data.transaction_issues.map((item) => (
            <TransactionIssueLine item={item} key={item.folio_id} />
          ))}
          title="Transaction issues"
        />
      </div>
    </section>
  );
}
