import type { ReactNode } from "react";
import Badge from "@/components/Badge";
import type { BusinessReviewResponse } from "@/lib/types";

type ReviewStatus = BusinessReviewResponse["review_status"];

function ProgressBar({ value }: { value: number }) {
  return (
    <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-parchment-50/[0.06]">
      <div
        className="h-full rounded-full bg-copper-400/75"
        style={{ width: `${Math.max(0, Math.min(100, value))}%` }}
      />
    </div>
  );
}

function StatusCard({
  title,
  note,
  children,
}: {
  title: string;
  note: string;
  children: ReactNode;
}) {
  return (
    <section className="panel-inset p-4">
      <h3 className="text-sm font-semibold text-parchment-100">{title}</h3>
      <p className="mt-1 text-[11px] leading-5 text-parchment-400">{note}</p>
      <div className="mt-3">{children}</div>
    </section>
  );
}

function Fact({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-warm-100/10 bg-parchment-50/[0.025] px-3 py-2">
      <p className="text-[10px] uppercase tracking-[0.12em] text-parchment-400">
        {label}
      </p>
      <p className="mt-0.5 text-sm font-medium tabular-nums text-parchment-200">
        {value}
      </p>
    </div>
  );
}

export default function ReviewStatusPanel({ data }: { data: ReviewStatus }) {
  const mappings = data.mappings;
  const mappingCoverage = mappings.schemes
    ? (mappings.reviewed / mappings.schemes) * 100
    : 0;
  const comparisons = data.comparisons;
  const coverage = data.coverage;

  return (
    <section>
      <div className="mb-3">
        <h2 className="text-base font-semibold text-parchment-100">
          Review status and coverage
        </h2>
        <p className="mt-1 text-xs leading-5 text-parchment-400">
          A quick read on whether the local snapshot is ready for business
          decisions. Reviewed mappings and complete levels are required before a
          comparison can be used.
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <StatusCard
          note="Only reviewed mappings are used for benchmark comparisons."
          title="Mapping review"
        >
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-2xl font-semibold tabular-nums text-parchment-50">
              {mappings.reviewed}
              <span className="text-sm font-normal text-parchment-400">
                {" "}
                / {mappings.schemes}
              </span>
            </p>
            <span className="text-[11px] text-parchment-400">reviewed</span>
          </div>
          <ProgressBar value={mappingCoverage} />
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Badge tone="blue">{mappings.reviewed} reviewed</Badge>
            <Badge tone={mappings.needs_review > 0 ? "amber" : "slate"}>
              {mappings.needs_review} need review
            </Badge>
            <Badge tone={mappings.unmapped > 0 ? "amber" : "slate"}>
              {mappings.unmapped} unmapped
            </Badge>
          </div>
        </StatusCard>

        <StatusCard
          note="Comparisons available from the existing folio and benchmark results."
          title="Comparison coverage"
        >
          <div className="flex items-baseline justify-between gap-3">
            <p className="text-2xl font-semibold tabular-nums text-parchment-50">
              {comparisons.available}
              <span className="text-sm font-normal text-parchment-400">
                {" "}
                / {coverage.folios}
              </span>
            </p>
            <span className="text-[11px] text-parchment-400">
              {comparisons.coverage_percent.toFixed(1)}%
            </span>
          </div>
          <ProgressBar value={comparisons.coverage_percent} />
          <div className="mt-3 flex flex-wrap gap-1.5">
            <Badge tone="green">{comparisons.ahead} ahead</Badge>
            <Badge tone="red">{comparisons.behind} behind</Badge>
            <Badge tone={comparisons.needs_review > 0 ? "amber" : "slate"}>
              {comparisons.needs_review} review
            </Badge>
            <Badge tone="slate">{comparisons.not_available} not available</Badge>
          </div>
        </StatusCard>

        <StatusCard
          note="Coverage of the local snapshot used by the review."
          title="Data coverage"
        >
          <div className="grid grid-cols-2 gap-2">
            <Fact label="Clients" value={String(coverage.clients)} />
            <Fact label="Folios" value={String(coverage.folios)} />
            <Fact label="Portfolio rows" value={String(coverage.portfolio_rows)} />
            <Fact label="Transactions" value={String(coverage.transactions)} />
            <Fact
              label="XIRR available"
              value={`${coverage.xirr_available} / ${coverage.folios}`}
            />
            <Fact
              label="Current value"
              value={`${coverage.folio_value_available} / ${coverage.folios}`}
            />
          </div>
          {(coverage.transactions_unmatched > 0 ||
            coverage.unknown_transactions > 0 ||
            coverage.missing_transaction_dates > 0 ||
            coverage.missing_transaction_amounts > 0) && (
            <p className="mt-2 text-[10px] leading-4 text-amber-300">
              {coverage.transactions_unmatched} unmatched transaction(s) ·{" "}
              {coverage.unknown_transactions} unknown type(s) ·{" "}
              {coverage.missing_transaction_dates} missing date(s) ·{" "}
              {coverage.missing_transaction_amounts} missing amount(s)
            </p>
          )}
        </StatusCard>

        <StatusCard
          note="Locally imported closing levels. Nothing is fetched from the web."
          title="Benchmark data"
        >
          <div className="grid grid-cols-2 gap-2">
            <Fact label="Series" value={String(data.benchmark_data.series)} />
            <Fact label="Levels" value={String(data.benchmark_data.levels)} />
          </div>
          {data.benchmark_data.series_names.length > 0 ? (
            <p className="mt-2 line-clamp-3 text-[10px] leading-4 text-parchment-400">
              {data.benchmark_data.series_names.join(" · ")}
            </p>
          ) : (
            <p className="mt-2 text-[10px] leading-4 text-parchment-400">
              No local benchmark levels imported yet.
            </p>
          )}
        </StatusCard>
      </div>
    </section>
  );
}
