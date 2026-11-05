"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import AppNav from "@/components/AppNav";
import BusinessConcentration from "@/components/BusinessConcentration";
import BusinessReviewTable from "@/components/BusinessReviewTable";
import DataQualityReview from "@/components/DataQualityReview";
import ReviewStatusPanel from "@/components/ReviewStatusPanel";
import { api } from "@/lib/api";
import { formatCurrency, formatDate } from "@/lib/format";
import type { BusinessReviewResponse } from "@/lib/types";

const sortLabels: Record<string, string> = {
  current_value: "current value",
  difference: "difference",
  xirr: "XIRR",
  client_name: "client name",
};

function SummaryCard({
  label,
  value,
  note,
  tone = "text-parchment-50",
}: {
  label: string;
  value: string | number;
  note: string;
  tone?: string;
}) {
  return (
    <div className="glass-panel px-4 py-3.5">
      <p className="eyebrow">{label}</p>
      <p className={`mt-1.5 text-2xl font-semibold tracking-tight ${tone}`}>
        {typeof value === "number" ? value.toLocaleString("en-IN") : value}
      </p>
      <p className="mt-0.5 text-[10px] leading-4 text-parchment-400">{note}</p>
    </div>
  );
}

export default function BusinessReviewClient() {
  const [data, setData] = useState<BusinessReviewResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [performance, setPerformance] = useState("behind");
  const [benchmark, setBenchmark] = useState("all");
  const [client, setClient] = useState("all");
  const [minimumInput, setMinimumInput] = useState("");
  const [minimum, setMinimum] = useState<number | null>(null);
  const [sort, setSort] = useState("current_value");
  const [direction, setDirection] = useState("desc");
  const requestId = useRef(0);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      const trimmed = minimumInput.trim();
      if (!trimmed) {
        setMinimum(null);
        return;
      }
      const parsed = Number(trimmed);
      setMinimum(
        Number.isFinite(parsed) && parsed >= 0 ? parsed : null,
      );
    }, 350);
    return () => window.clearTimeout(timer);
  }, [minimumInput]);

  const refresh = useCallback(async () => {
    const currentRequest = requestId.current + 1;
    requestId.current = currentRequest;
    setLoading(true);
    try {
      const payload = await api.businessReview({
        performance,
        benchmark,
        client,
        minCurrentValue: minimum,
        sort,
        direction,
      });
      if (requestId.current === currentRequest) {
        setData(payload);
        setError(null);
      }
    } catch (err) {
      if (requestId.current === currentRequest) {
        setError(
          err instanceof Error
            ? `${err.message}. Make sure the local API is running at ${api.baseUrl}.`
            : "Could not load the Business Review.",
        );
      }
    } finally {
      if (requestId.current === currentRequest) setLoading(false);
    }
  }, [benchmark, client, direction, minimum, performance, sort]);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  function clearFilters() {
    setPerformance("all");
    setBenchmark("all");
    setClient("all");
    setMinimumInput("");
    setMinimum(null);
    setSort("current_value");
    setDirection("desc");
  }

  const hasData = data?.meta.has_data ?? false;
  const summary = data?.summary;
  const attention = data?.attention;
  const filtersCleared =
    performance === "all" &&
    benchmark === "all" &&
    client === "all" &&
    minimumInput.trim() === "" &&
    sort === "current_value" &&
    direction === "desc";
  const filterLine = attention
    ? `${attention.matching.toLocaleString("en-IN")} of ${attention.total_folios.toLocaleString("en-IN")} folios shown · sorted by ${sortLabels[sort]} (${direction === "desc" ? "descending" : "ascending"})`
    : "";

  return (
    <main className="mx-auto w-full max-w-[1700px] px-4 py-6 sm:px-6 lg:px-8">
      <header className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div>
          <div className="mb-3">
            <AppNav active="review" />
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-2xl font-semibold tracking-tight text-parchment-50 sm:text-3xl">
              Business Review
            </h1>
            <span className="rounded-full bg-sage-500/10 px-2.5 py-1 text-[11px] font-semibold text-sage-300 ring-1 ring-inset ring-sage-500/25">
              Local only
            </span>
            <span className="rounded-full bg-copper-400/10 px-2.5 py-1 text-[11px] font-semibold text-copper-300 ring-1 ring-inset ring-copper-400/25">
              Actionable review
            </span>
          </div>
          <p className="mt-2 max-w-3xl text-sm leading-5 text-parchment-400">
            A practical review of underperformers, data gaps, business
            concentration and review readiness. Everything is grouped from the
            existing local snapshot, folio calculations and benchmark comparison
            results; no new calculation or external fetch is added.
          </p>
        </div>
        <div className="panel px-4 py-3 text-xs text-parchment-400">
          <p className="font-medium text-parchment-200">Milestone 5.1</p>
          <p className="mt-1">
            Underperformers · data quality · concentration · coverage
          </p>
          <p className="mt-1">
            Green = ahead · red = behind · amber = review · grey = unavailable
          </p>
          {data?.meta.valuation_date && (
            <p className="mt-1 text-parchment-400">
              Valuation date: {formatDate(data.meta.valuation_date)}
            </p>
          )}
        </div>
      </header>

      {error && (
        <div className="mb-4 rounded-xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      )}

      {!hasData && !loading ? (
        <section className="panel flex flex-col items-center px-6 py-14 text-center">
          <span className="flex h-12 w-12 items-center justify-center rounded-full bg-copper-400/10 text-xl text-copper-300 ring-1 ring-inset ring-copper-400/25">
             ₹
          </span>
          <h2 className="mt-4 text-lg font-semibold text-parchment-100">
            No snapshot to review yet
          </h2>
          <p className="mx-auto mt-2 max-w-lg text-sm leading-6 text-parchment-400">
            Load the demo data or import the four InvestWell files on the
            Dashboard. The Business Review appears after a snapshot is confirmed.
          </p>
          <Link className="btn-primary mt-5 px-4 py-2 text-sm" href="/">
            Open Dashboard
          </Link>
        </section>
      ) : loading && !data ? (
        <div className="panel p-10 text-center text-sm text-parchment-400">
          Loading local Business Review…
        </div>
      ) : data && summary && attention ? (
        <div className="space-y-5">
          <div className="grid grid-cols-2 gap-2.5 md:grid-cols-3 xl:grid-cols-6">
            <SummaryCard
              label="Underperforming"
              note={
                summary.underperforming_value === null
                  ? "Folios behind their benchmark"
                  : `${formatCurrency(summary.underperforming_value)} current value in review`
              }
              tone="text-rose-300"
              value={summary.behind}
            />
            <SummaryCard
              label="Ahead"
              note="Folios ahead of benchmark"
              tone="text-emerald-300"
              value={summary.ahead}
            />
            <SummaryCard
              label="Needs review"
              note="Mapping or comparison review"
              tone="text-amber-300"
              value={summary.needs_review}
            />
            <SummaryCard
              label="Not available"
              note="No usable comparison"
              tone="text-parchment-300"
              value={summary.not_available}
            />
            <SummaryCard
              label="Data review"
              note={`${summary.data_quality_groups} group${summary.data_quality_groups === 1 ? "" : "s"} with items`}
              tone="text-amber-300"
              value={summary.data_quality_items}
            />
            <SummaryCard
              label="Comparable"
              note={`${summary.comparison_coverage.toFixed(1)}% coverage`}
              tone="text-copper-300"
              value={`${summary.comparisons_available} / ${summary.folios}`}
            />
          </div>

          <section className="panel p-4">
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
              <label className="block">
                <span className="eyebrow">Performance</span>
                <select
                  aria-label="Filter by performance status"
                  className="field mt-1.5 w-full px-3 py-2.5 text-sm"
                  onChange={(event) => setPerformance(event.target.value)}
                  value={performance}
                >
                  <option value="all">All statuses</option>
                  <option value="ahead">Ahead of benchmark</option>
                  <option value="behind">Behind benchmark</option>
                  <option value="in_line">In line with benchmark</option>
                  <option value="not_available">Not available</option>
                  <option value="needs_review">Needs review</option>
                </select>
              </label>

              <label className="block">
                <span className="eyebrow">Benchmark / category</span>
                <select
                  aria-label="Filter by benchmark or category"
                  className="field mt-1.5 w-full px-3 py-2.5 text-sm"
                  onChange={(event) => setBenchmark(event.target.value)}
                  value={benchmark}
                >
                  <option value="all">All benchmarks</option>
                  {attention.filter_options.benchmarks.map((item) => (
                    <option key={item.name} value={item.name}>
                      {item.name} ({item.count})
                    </option>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="eyebrow">Client</span>
                <select
                  aria-label="Filter by client"
                  className="field mt-1.5 w-full px-3 py-2.5 text-sm"
                  onChange={(event) => setClient(event.target.value)}
                  value={client}
                >
                  <option value="all">All clients</option>
                  {attention.filter_options.clients.map((item) => (
                    <option key={item.key} value={item.key}>
                      {item.name} ({item.count})
                    </option>
                  ))}
                </select>
              </label>

              <label className="block">
                <span className="eyebrow">Minimum current value</span>
                <div className="relative mt-1.5">
                  <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-sm text-parchment-400">
                    ₹
                  </span>
                  <input
                    aria-label="Minimum current value"
                    className="field w-full py-2.5 pl-7 pr-3 text-sm tabular-nums"
                    min="0"
                    onChange={(event) => setMinimumInput(event.target.value)}
                    placeholder="Any value"
                    step="10000"
                    type="number"
                    value={minimumInput}
                  />
                </div>
              </label>

              <label className="block">
                <span className="eyebrow">Sort by</span>
                <select
                  aria-label="Sort folios"
                  className="field mt-1.5 w-full px-3 py-2.5 text-sm"
                  onChange={(event) => setSort(event.target.value)}
                  value={sort}
                >
                  <option value="current_value">Current value</option>
                  <option value="difference">Difference</option>
                  <option value="xirr">XIRR</option>
                  <option value="client_name">Client name</option>
                </select>
              </label>

              <label className="block">
                <span className="eyebrow">Order</span>
                <select
                  aria-label="Sort direction"
                  className="field mt-1.5 w-full px-3 py-2.5 text-sm"
                  onChange={(event) => setDirection(event.target.value)}
                  value={direction}
                >
                  <option value="desc">Descending</option>
                  <option value="asc">Ascending</option>
                </select>
              </label>
            </div>

            <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-warm-100/10 pt-3 text-xs text-parchment-400">
              <span>{filterLine}</span>
              {loading && <span className="text-copper-300">Updating…</span>}
              <span className="text-parchment-600">·</span>
              <button
                className="font-medium text-copper-300 hover:text-copper-200 disabled:cursor-not-allowed disabled:text-parchment-500 disabled:hover:text-parchment-500"
                disabled={performance === "behind"}
                onClick={() => setPerformance("behind")}
                title={
                  performance === "behind"
                    ? "Only underperforming folios are already shown"
                    : "Show only folios behind their benchmark"
                }
                type="button"
              >
                Show only underperformers
              </button>
              <button
                className="font-medium text-copper-300 hover:text-copper-200 disabled:cursor-not-allowed disabled:text-parchment-500 disabled:hover:text-parchment-500"
                disabled={performance === "all"}
                onClick={() => setPerformance("all")}
                title={
                  performance === "all"
                    ? "All performance states are already shown"
                    : "Show every performance state"
                }
                type="button"
              >
                Show all statuses
              </button>
              <button
                className="font-medium text-copper-300 hover:text-copper-200 disabled:cursor-not-allowed disabled:text-parchment-500 disabled:hover:text-parchment-500"
                disabled={filtersCleared}
                onClick={clearFilters}
                title={
                  filtersCleared
                    ? "Filters are already cleared to all statuses"
                    : "Reset every filter and sort control"
                }
                type="button"
              >
                Clear filters
              </button>
              {(performance !== "behind" ||
                benchmark !== "all" ||
                client !== "all" ||
                minimumInput.trim() !== "" ||
                sort !== "current_value" ||
                direction !== "desc") && (
                <span className="rounded-full border border-copper-400/20 bg-copper-400/10 px-2 py-0.5 text-[10px] font-medium text-copper-200">
                  Filters active
                </span>
              )}
            </div>
          </section>

          <section className="panel overflow-hidden">
            <div className="flex flex-col gap-3 border-b border-warm-100/15 px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <h2 className="text-base font-semibold text-parchment-100">
                    Folios needing attention
                  </h2>
                  <span className="rounded-full border border-warm-100/15 bg-parchment-50/[0.045] px-2.5 py-1 text-[11px] font-medium text-parchment-300">
                    {attention.matching.toLocaleString("en-IN")} shown
                  </span>
                </div>
                <p className="mt-1 max-w-3xl text-xs leading-5 text-parchment-400">
                  The default view lists underperforming folios with the largest
                  current value first. Use the filters to focus on a benchmark,
                  client, performance state or material holding size.
                </p>
              </div>
              <Link className="btn-secondary shrink-0 px-3 py-1.5 text-xs" href="/graph">
                Open graph
              </Link>
            </div>
            <BusinessReviewTable
              onClearFilters={clearFilters}
              rows={attention.folios}
            />
          </section>

          <DataQualityReview data={data.data_quality} />
          <BusinessConcentration data={data.concentration} />
          <ReviewStatusPanel data={data.review_status} />
        </div>
      ) : null}

      <footer className="mt-8 flex flex-col gap-2 border-t border-warm-100/15 pt-4 text-xs text-parchment-400 sm:flex-row sm:items-center sm:justify-between">
        <p>
          Business Review is read-only. It groups the existing local folio
          calculations, benchmark comparisons and mappings; it never repairs or
          estimates missing values.
        </p>
        <p>
          {data?.meta.has_data
            ? "Source: local SQLite snapshot."
            : "No snapshot loaded."}
        </p>
      </footer>
    </main>
  );
}
