"use client";

import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";
import AppNav from "@/components/AppNav";
import Badge from "@/components/Badge";
import { api } from "@/lib/api";
import type {
  BenchmarkCoverageSeries,
  BenchmarkLevelImportResponse,
  BenchmarkLevelsResponse,
  BenchmarkMappingItem,
  BenchmarkMappingResponse,
  BenchmarkMappingStatusSummary,
  BenchmarkMappingSummary,
  KeywordMappingPreview,
  MappingFilePreview,
} from "@/lib/types";
import {
  keywordPreviewLabel,
  mappingImportLabel,
  setVisibleSchemeSelection,
  suggestionAcceptTargets,
  summarizeMappings,
  toggleSchemeSelection,
} from "@/lib/mappingTools";
import { formatFileSize, validateUploadFile } from "@/lib/upload";
import { SearchableSelect } from "@/components/SearchableSelect";

function mergeChangeResult(
  current: BenchmarkMappingResponse | null,
  result: {
    mappings?: BenchmarkMappingItem[];
    summary?: BenchmarkMappingSummary;
    status_summary?: BenchmarkMappingStatusSummary;
    available_benchmarks?: string[];
    coverage?: BenchmarkMappingResponse["coverage"];
  },
): BenchmarkMappingResponse | null {
  if (!current) return current;
  const mappings = result.mappings ?? current.mappings;
  const derived = summarizeMappings(mappings);
  return {
    mappings,
    available_benchmarks:
      result.available_benchmarks ?? current.available_benchmarks,
    coverage: result.coverage ?? current.coverage,
    summary: result.summary ?? derived.summary,
    status_summary: result.status_summary ?? derived.status_summary,
  };
}

function formatDate(value: string | null): string {
  if (!value) return "Not available";
  return new Date(`${value.slice(0, 10)}T00:00:00`).toLocaleDateString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function formatDateTime(value: string | null): string {
  if (!value) return "Not available";
  return new Date(value).toLocaleString("en-IN", {
    day: "2-digit",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function MappingStatusBadge({ item }: { item: BenchmarkMappingItem }) {
  if (item.review_status === "reviewed") {
    return <Badge tone="blue">Reviewed</Badge>;
  }
  if (item.review_status === "needs_mapping") {
    return <Badge tone="amber">Needs mapping</Badge>;
  }
  return <Badge tone="amber">Needs Review</Badge>;
}

function CoverageBadge({
  status,
}: {
  status: string;
}) {
  if (status === "covered") {
    return <Badge tone="green">Dates covered</Badge>;
  }
  if (status === "missing_dates") {
    return <Badge tone="amber">Missing dates</Badge>;
  }
  if (status === "no_levels") {
    return <Badge tone="red">No local levels</Badge>;
  }
  if (status === "no_required_dates") {
    return <Badge tone="slate">No required dates</Badge>;
  }
  if (status === "needs_mapping") {
    return <Badge tone="amber">Needs mapping</Badge>;
  }
  if (status === "needs_review") {
    return <Badge tone="amber">Needs review</Badge>;
  }
  if (status === "no_transactions") {
    return <Badge tone="slate">No transactions</Badge>;
  }
  return <Badge tone="slate">Not checked</Badge>;
}

function DateList({
  dates,
  empty,
  limit = 8,
}: {
  dates: string[];
  empty: string;
  limit?: number;
}) {
  if (dates.length === 0) {
    return <span className="text-parchment-400">{empty}</span>;
  }
  const visible = dates.slice(0, limit);
  return (
    <span>
      {visible.map((item) => formatDate(item)).join(", ")}
      {dates.length > visible.length ? (
        <details className="mt-1">
          <summary className="cursor-pointer text-copper-300">
            Show all {dates.length.toLocaleString("en-IN")} dates
          </summary>
          <span className="mt-1 block max-h-40 overflow-auto leading-5 text-parchment-400">
            {dates.map((item) => formatDate(item)).join(", ")}
          </span>
        </details>
      ) : null}
    </span>
  );
}

function CoverageSeriesCard({ item }: { item: BenchmarkCoverageSeries }) {
  const needsAttention =
    item.coverage_status === "missing_dates" ||
    item.coverage_status === "no_levels";
  return (
    <div
      className={
        needsAttention
          ? "rounded-xl border border-amber-400/30 bg-amber-400/[0.05] p-4"
          : "rounded-xl border border-warm-100/15 bg-parchment-50/[0.035] p-4"
      }
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="font-semibold text-parchment-100">{item.benchmark_name}</p>
          <p className="mt-1 text-[11px] text-parchment-400">
            {item.scheme_count.toLocaleString("en-IN")} scheme(s) ·{" "}
            {item.folio_count.toLocaleString("en-IN")} folio(s)
            {item.comparison_method
              ? ` · ${item.comparison_method.replaceAll("_", " ")}`
              : ""}
        </p>
        </div>
        <CoverageBadge status={item.coverage_status} />
      </div>
      <dl className="mt-3 space-y-1 text-xs">
        <div className="flex gap-2">
          <dt className="w-32 shrink-0 text-parchment-500">Required dates</dt>
          <dd className="text-parchment-300">
            {item.required_date_count.toLocaleString("en-IN")}
            {item.available_date_count
              ? ` · ${item.available_date_count.toLocaleString("en-IN")} local dates`
              : ""}
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-32 shrink-0 text-parchment-500">Valuation date</dt>
          <dd
            className={
              item.covers_valuation_date === false
                ? "font-medium text-rose-300"
                : "text-parchment-300"
            }
          >
            {item.covers_valuation_date === null
              ? "Not required"
              : item.covers_valuation_date
              ? "Covered"
              : "Missing"}
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-32 shrink-0 text-parchment-500">First transaction</dt>
          <dd
            className={
              item.covers_first_transaction === false
                ? "font-medium text-rose-300"
                : "text-parchment-300"
            }
          >
            {item.covers_first_transaction === null
              ? "Not required"
              : item.covers_first_transaction
              ? "Covered"
              : "Missing"}
          </dd>
        </div>
        <div className="flex gap-2">
          <dt className="w-32 shrink-0 text-parchment-500">Missing dates</dt>
          <dd className="min-w-0 text-parchment-300">
            <DateList
              dates={item.missing_dates}
              empty={
                item.required_date_count === 0
                  ? "No dated comparison flows"
                  : "None — all required dates covered"
              }
            />
          </dd>
        </div>
        {item.needs_review_count > 0 ? (
          <div className="flex gap-2">
            <dt className="w-32 shrink-0 text-parchment-500">Needs review</dt>
            <dd className="text-amber-300">
              {item.needs_review_count} mapped scheme(s) still need review
            </dd>
          </div>
        ) : null}
      </dl>
    </div>
  );
}

function SummaryCard({
  label,
  value,
  note,
  onClick,
}: {
  label: string;
  value: string | number;
  note?: string;
  onClick?: () => void;
}) {
  const Tag = onClick ? "button" : "div";
  return (
    <Tag
      type={onClick ? "button" : undefined}
      onClick={onClick}
      className={`glass-panel relative overflow-hidden px-5 py-4 transition-colors ${
        onClick
          ? "cursor-pointer hover:border-copper-400/30 hover:bg-parchment-50/10"
          : ""
      }`}
      aria-pressed={onClick ? false : undefined}
    >
      <span
        aria-hidden
        className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-copper-400/60 via-copper-400/10 to-transparent"
      />
      <p className="eyebrow">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-parchment-50">
        {typeof value === "number" ? value.toLocaleString("en-IN") : value}
      </p>
      {note && <p className="mt-1 text-[11px] text-parchment-400">{note}</p>}
    </Tag>
  );
}

function sourceLabel(source: string): string {
  switch (source) {
    case "manual":
      return "Manual review";
    case "auto":
      return "Automatic suggestion";
    case "bulk":
      return "Bulk applied";
    case "accepted_suggestion":
      return "Accepted suggestion";
    case "keyword_rule":
      return "Keyword rule";
    case "imported_file":
      return "Imported mapping file";
    default:
      return "No mapping";
  }
}

export default function BenchmarkClient() {
  const [mappings, setMappings] = useState<BenchmarkMappingResponse | null>(null);
  const [levels, setLevels] = useState<BenchmarkLevelsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedSchemeIds, setSelectedSchemeIds] = useState<Set<number>>(
    new Set(),
  );
  const [bulkBenchmark, setBulkBenchmark] = useState("");
  const [unmappedSelected, setUnmappedSelected] = useState<Set<number>>(new Set());
  const [unmappedBulkBenchmark, setUnmappedBulkBenchmark] = useState("");

  const load = useCallback(async (showSpinner = true) => {
    if (showSpinner) setLoading(true);
    try {
      const [mappingData, levelData] = await Promise.all([
        api.benchmarkMappings(),
        api.benchmarkLevels(),
      ]);
      setMappings(mappingData);
      setLevels(levelData);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? `${err.message}. Make sure the local API is running at ${api.baseUrl}.`
          : "Could not load benchmark settings.",
      );
    } finally {
      if (showSpinner) setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const filteredMappings = useMemo(() => {
    if (!mappings) return [];
    const search = query.trim().toLowerCase();
    return mappings.mappings.filter((item) => {
      if (
        statusFilter !== "all" &&
        item.review_status !== statusFilter
      ) {
        return false;
      }
      if (!search) return true;
      return (
        item.scheme_name.toLowerCase().includes(search) ||
        item.normalized_scheme_name.toLowerCase().includes(search) ||
        item.benchmark_name.toLowerCase().includes(search)
      );
    });
  }, [mappings, query, statusFilter]);

  const mappingSummary = mappings?.summary;
  const statusSummary = mappings?.status_summary;
  const levelSummaries = levels?.summaries ?? [];
  const visibleSchemeIds = filteredMappings.map((item) => item.scheme_id);
  const allVisibleSelected =
    visibleSchemeIds.length > 0 &&
    visibleSchemeIds.every((schemeId) => selectedSchemeIds.has(schemeId));
  const selectedFolios = (mappings?.mappings ?? [])
    .filter((item) => selectedSchemeIds.has(item.scheme_id))
    .reduce((total, item) => total + item.folio_count, 0);
  const acceptSuggestionIds = useMemo(
    () =>
      suggestionAcceptTargets(
        selectedSchemeIds,
        selectedSchemeIds.size > 0
          ? (mappings?.mappings ?? [])
          : filteredMappings,
      ),
    [filteredMappings, mappings, selectedSchemeIds],
  );

  const unmappedMappings = useMemo(
    () =>
      (mappings?.mappings ?? []).filter(
        (item) => item.review_status === "needs_mapping"
      ),
    [mappings],
  );

  const unmappedSchemeIds = useMemo(
    () => unmappedMappings.map((item) => item.scheme_id),
    [unmappedMappings],
  );

  const unmappedAllSelected =
    unmappedMappings.length > 0 &&
    unmappedMappings.every((item) => unmappedSelected.has(item.scheme_id));

  async function handleSave(item: BenchmarkMappingItem, value: string) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.updateBenchmarkMapping(item.scheme_id, value);
      setMappings((current) =>
        mergeChangeResult(current, {
          mappings: (current?.mappings ?? []).map((row) =>
            row.scheme_id === result.mapping.scheme_id ? result.mapping : row,
          ),
          available_benchmarks: result.available_benchmarks,
          summary: result.summary as BenchmarkMappingSummary,
          status_summary: result.status_summary,
          coverage: result.coverage,
        }),
      );
      setNotice(
        item.review_status === "reviewed"
          ? `Mapping saved for ${item.scheme_name}. Future comparisons will use the new benchmark.`
          : `Mapping saved for ${item.scheme_name}. The Needs Review badge was removed.`,
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not save the mapping.");
    } finally {
      setBusy(false);
    }
  }

  function movedLabel(result: {
    folios_moved_out_of_unmapped: number;
    unmapped_folios: number;
  }): string {
    const moved = result.folios_moved_out_of_unmapped.toLocaleString("en-IN");
    const remaining = result.unmapped_folios.toLocaleString("en-IN");
    return (
      `${moved} folio(s) moved out of Other / Unmapped. ` +
      `Unmapped folios remaining: ${remaining}.`
    );
  }

  function handleToggleSelected(schemeId: number) {
    setSelectedSchemeIds((current) =>
      toggleSchemeSelection(current, schemeId),
    );
  }

  async function handleBulkApply() {
    if (selectedSchemeIds.size === 0) {
      setError("Select at least one scheme before applying a benchmark.");
      return;
    }
    if (!bulkBenchmark) {
      setError("Choose a benchmark to apply to the selected schemes.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.bulkUpdateBenchmarkMappings(
        [...selectedSchemeIds],
        bulkBenchmark,
      );
      setMappings((current) => mergeChangeResult(current, result));
      setNotice(
        `Applied ${bulkBenchmark} to ${result.updated_schemes.toLocaleString(
          "en-IN",
        )} scheme(s) and ${result.updated_folios.toLocaleString("en-IN")} folio(s). ` +
          movedLabel(result),
      );
      setSelectedSchemeIds(new Set());
      setBulkBenchmark("");
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not apply the bulk mapping.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleAcceptSuggestions(schemeIds: number[]) {
    if (schemeIds.length === 0) {
      setError(
        "No visible automatic suggestions are available to accept. Change the filter or select a scheme with a suggestion.",
      );
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.acceptBenchmarkSuggestions(schemeIds);
      setMappings((current) => mergeChangeResult(current, result));
      const accepted = result.accepted_schemes ?? result.updated_schemes;
      setNotice(
        accepted === 0
          ? "No unreviewed suggestions were available to accept. Nothing changed."
          : `Accepted ${accepted.toLocaleString(
              "en-IN",
            )} visible suggestion(s) for ${result.updated_folios.toLocaleString(
              "en-IN",
            )} folio(s). ` + movedLabel(result),
      );
      if (accepted > 0) setSelectedSchemeIds(new Set());
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not accept the automatic suggestions.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleAcceptHighConfidence() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.acceptHighConfidenceSuggestions();
      setMappings((current) => mergeChangeResult(current, result));
      const accepted = result.accepted_schemes ?? result.updated_schemes;
      setNotice(
        accepted === 0
          ? "No high-confidence automatic suggestions were available to accept. Nothing changed."
          : `Accepted ${accepted.toLocaleString(
              "en-IN",
            )} high-confidence suggestion(s) for ${result.updated_folios.toLocaleString(
              "en-IN",
            )} folio(s). ` + movedLabel(result),
      );
      if (accepted > 0) setSelectedSchemeIds(new Set());
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Could not accept the high-confidence suggestions.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleRefreshBenchmarkLevels() {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.refreshBenchmarkLevels(5);
      setNotice(
        `TRI refresh: ${result.succeeded} succeeded, ${result.failed} failed, ${result.attempted} attempted. Date range: ${result.date_range.from} to ${result.date_range.to}.` +
          (result.errors.length > 0
            ? ` Errors: ${result.errors.map((e: { error: string }) => e.error).join(", ")}`
            : ""),
      );
      await load(false);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not refresh benchmark levels.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleUnmappedBulkApply(benchmarkName: string) {
    if (unmappedSelected.size === 0) {
      setError("Select at least one unmapped scheme before applying a benchmark.");
      return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await api.bulkUpdateBenchmarkMappings(
        [...unmappedSelected],
        benchmarkName,
      );
      setMappings((current) => mergeChangeResult(current, result));
      setNotice(
        `Applied ${benchmarkName} to ${result.updated_schemes.toLocaleString(
          "en-IN",
        )} unmapped scheme(s) and ${result.updated_folios.toLocaleString(
          "en-IN",
        )} folio(s). ` + movedLabel(result),
      );
      setUnmappedSelected(new Set());
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Could not apply the bulk mapping.",
      );
    } finally {
      setBusy(false);
    }
  }

  async function handleUnmappedBulkApplyFromDropdown() {
    if (unmappedSelected.size === 0) {
      setError("Select at least one unmapped scheme before applying a benchmark.");
      return;
    }
    if (!unmappedBulkBenchmark) {
      setError("Choose a benchmark to apply to the selected unmapped schemes.");
      return;
    }
    await handleUnmappedBulkApply(unmappedBulkBenchmark);
  }

  return (
    <main className="mx-auto w-full max-w-[1700px] px-4 py-6 sm:px-6 lg:px-8">
      <header className="mb-6">
        <div className="mb-3">
          <AppNav active="benchmarks" />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight text-parchment-50 sm:text-3xl">
            Benchmark Mapping & Data
          </h1>
          <span className="rounded-full bg-sage-500/10 px-2.5 py-1 text-[11px] font-semibold text-sage-300 ring-1 ring-inset ring-sage-500/25">
            Local only
          </span>
        </div>
        <p className="mt-2 max-w-4xl text-sm text-parchment-400">
          Review each scheme&apos;s benchmark. Automatic suggestions stay amber until
          you approve them. Nothing is fetched from the internet, and missing dates
          are never filled.
        </p>
      </header>

      {error && (
        <div className="mb-4 rounded-xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      )}
      {notice && (
        <div className="mb-4 rounded-xl border border-copper-400/30 bg-copper-500/10 px-4 py-3 text-sm text-copper-200">
          {notice}
        </div>
      )}

      {loading && !mappings ? (
        <div className="panel p-10 text-center text-sm text-parchment-400">
          Loading local benchmark settings...
        </div>
      ) : (
        <div className="space-y-5">
          <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-6">
            <SummaryCard
              label="Total schemes"
              value={statusSummary?.total_schemes ?? 0}
              note={`${(statusSummary?.total_folios ?? 0).toLocaleString("en-IN")} folios in the latest snapshot`}
              onClick={() => document.getElementById("review-scheme-mappings")?.scrollIntoView({ behavior: "smooth" })}
            />
            <SummaryCard
              label="Mapped schemes"
              value={statusSummary?.mapped_schemes ?? 0}
              note={`${(statusSummary?.mapped_folios ?? 0).toLocaleString("en-IN")} folios use a benchmark`}
              onClick={() => document.getElementById("review-scheme-mappings")?.scrollIntoView({ behavior: "smooth" })}
            />
            <SummaryCard
              label="Needs review"
              value={statusSummary?.needs_review_schemes ?? 0}
              note={`${(statusSummary?.needs_review_folios ?? 0).toLocaleString("en-IN")} folios waiting for approval`}
              onClick={() => {
                document.getElementById("review-scheme-mappings")?.scrollIntoView({ behavior: "smooth" });
                setStatusFilter("needs_review");
              }}
            />
            <SummaryCard
              label="Unmapped schemes"
              value={statusSummary?.unmapped_schemes ?? 0}
              note="shown as Other / Unmapped"
              onClick={() => {
                document.getElementById("review-scheme-mappings")?.scrollIntoView({ behavior: "smooth" });
                setStatusFilter("needs_mapping");
              }}
            />
            <SummaryCard
              label="Folios in unmapped schemes"
              value={statusSummary?.unmapped_folios ?? 0}
              note="move out of Other / Unmapped when mapped"
              onClick={() => {
                document.getElementById("review-scheme-mappings")?.scrollIntoView({ behavior: "smooth" });
                setStatusFilter("needs_mapping");
              }}
            />
            <SummaryCard
              label="TRI data status"
              value={levels?.total_benchmarks ?? 0}
              note={
                levels?.total_benchmarks === 0
                  ? "No TRI data — click to refresh"
                  : `${(levels?.total_levels ?? 0).toLocaleString("en-IN")} dated levels · ${mappings?.coverage.summary.series_missing_dates ?? 0} with gaps`
              }
              onClick={() => document.getElementById("refresh-tri")?.scrollIntoView({ behavior: "smooth" })}
            />
          </section>

          <section id="review-scheme-mappings" className="panel overflow-hidden">
            <div className="flex flex-col gap-3 border-b border-warm-100/15 px-5 py-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h2 className="text-base font-semibold text-parchment-100">
                  1. Review scheme mappings
                </h2>
                <p className="mt-1 text-xs text-parchment-400">
                  Every mapping is saved per scheme and applies to all of its folios.
                  Approving the current suggestion removes its Needs Review badge; the
                  suggestion source is always shown so nothing is guessed silently.
                </p>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <input
                  aria-label="Search schemes"
                  className="field min-w-[240px] px-3 py-2 text-sm"
                  onChange={(event) => setQuery(event.target.value)}
                  placeholder="Search scheme, code or benchmark"
                  type="search"
                  value={query}
                />
                <SearchableSelect
                  options={["all", "needs_review", "reviewed", "needs_mapping"]}
                  value={statusFilter}
                  onChange={setStatusFilter}
                  placeholder="All statuses"
                />
              </div>
            </div>

            {!mappingSummary || mappingSummary.schemes === 0 ? (
              <div className="px-5 py-10 text-center">
                <p className="text-sm text-parchment-300">No schemes imported yet.</p>
                <p className="mt-1 text-xs text-parchment-400">
                  Confirm an InvestWell snapshot in Upload first.
                </p>
                <Link className="btn-secondary mt-4 inline-flex" href="/">
                  Go to Upload
                </Link>
              </div>
            ) : (
              <>
                <div className="flex flex-wrap items-center gap-3 border-b border-warm-100/15 px-5 py-3 text-xs text-parchment-400">
                  <span>
                    Showing {filteredMappings.length} of {mappings?.mappings.length ?? 0}{" "}
                    schemes
                  </span>
                  <span className="text-parchment-600">·</span>
                  <span>{mappingSummary.reviewed} reviewed</span>
                  <span className="text-parchment-600">·</span>
                  <span>
                    {mappingSummary.needs_review}{" "}
                    {mappingSummary.needs_review === 1 ? "needs" : "need"} review
                  </span>
                  {mappingSummary.unmapped > 0 && (
                    <>
                      <span className="text-parchment-600">·</span>
                      <span>{mappingSummary.unmapped} unmapped</span>
                    </>
                  )}
                </div>
                <div className="flex flex-col gap-3 border-b border-warm-100/15 bg-ink-900/40 px-5 py-3 lg:flex-row lg:items-center lg:justify-between">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-parchment-300">
                    <span className="font-semibold text-parchment-100">
                      {selectedSchemeIds.size.toLocaleString("en-IN")} selected
                    </span>
                    <span className="text-parchment-500">
                      · {selectedFolios.toLocaleString("en-IN")} folios affected
                    </span>
                    <button
                      className="font-medium text-copper-300 hover:text-copper-200 disabled:cursor-not-allowed disabled:text-parchment-600"
                      disabled={busy || selectedSchemeIds.size === 0}
                      onClick={() => setSelectedSchemeIds(new Set())}
                      type="button"
                    >
                      Clear
                    </button>
                    <button
                      className="font-medium text-copper-300 hover:text-copper-200 disabled:cursor-not-allowed disabled:text-parchment-600"
                      disabled={busy || visibleSchemeIds.length === 0}
                      onClick={() =>
                        setSelectedSchemeIds(new Set(visibleSchemeIds))
                      }
                      type="button"
                    >
                      Select filtered ({visibleSchemeIds.length.toLocaleString("en-IN")})
                    </button>
                  </div>
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                    <SearchableSelect
                      label="Benchmark for selected schemes"
                      options={mappings?.available_benchmarks ?? []}
                      value={bulkBenchmark}
                      onChange={setBulkBenchmark}
                      placeholder="Benchmark for selected schemes…"
                    />
                    <button
                      className="btn-primary whitespace-nowrap px-3 py-2 text-xs"
                      disabled={
                        busy || selectedSchemeIds.size === 0 || !bulkBenchmark
                      }
                      onClick={() => void handleBulkApply()}
                      title="Apply one benchmark to every selected scheme and all of their folios"
                      type="button"
                    >
                      {busy ? "Applying…" : "Apply to selected"}
                    </button>
                    <button
                      className="btn-secondary whitespace-nowrap px-3 py-2 text-xs"
                      disabled={busy || acceptSuggestionIds.length === 0}
                      onClick={() =>
                        void handleAcceptSuggestions(acceptSuggestionIds)
                      }
                      title={
                        acceptSuggestionIds.length === 0
                          ? "No visible automatic suggestions match the current selection or filter"
                          : selectedSchemeIds.size > 0
                          ? `Accept the ${acceptSuggestionIds.length.toLocaleString("en-IN")} automatic suggestion(s) in the selected schemes`
                          : `Accept the ${acceptSuggestionIds.length.toLocaleString("en-IN")} automatic suggestion(s) visible in the current filter`
                      }
                      type="button"
                    >
                      Accept suggestions (
                      {acceptSuggestionIds.length.toLocaleString("en-IN")})
                    </button>
                    <button
                      className="btn-primary whitespace-nowrap px-3 py-2 text-xs"
                      disabled={busy}
                      onClick={() => void handleAcceptHighConfidence()}
                      title="Apply all high-confidence automatic suggestions (category keyword matches) across all schemes"
                      type="button"
                    >
                      Apply All High-Confidence Suggestions
                    </button>
                  </div>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[1380px] border-collapse text-left text-sm">
                    <thead className="bg-ink-900/80 text-[11px] uppercase tracking-[0.14em] text-parchment-400">
                      <tr>
                        <th className="w-10 px-3 py-3">
                          <input
                            aria-label="Select all filtered schemes"
                            checked={allVisibleSelected}
                            className="h-4 w-4 cursor-pointer accent-copper-500"
                            disabled={visibleSchemeIds.length === 0}
                            onChange={(event) =>
                              setSelectedSchemeIds((current) =>
                                setVisibleSchemeSelection(
                                  current,
                                  visibleSchemeIds,
                                  event.target.checked,
                                ),
                              )
                            }
                            type="checkbox"
                          />
                        </th>
                        <th className="px-4 py-3 font-semibold">Scheme</th>
                        <th className="px-4 py-3 text-right font-semibold">Folios</th>
                        <th className="px-4 py-3 font-semibold">Benchmark mapping</th>
                        <th className="px-4 py-3 font-semibold">Review status</th>
                        <th className="px-4 py-3 text-right font-semibold">Action</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-warm-100/10">
                      {filteredMappings.map((item) => (
                        <MappingRow
                          busy={busy}
                          item={item}
                          key={item.scheme_id}
                          onSave={handleSave}
                          onToggleSelected={handleToggleSelected}
                          options={mappings?.available_benchmarks ?? []}
                          selected={selectedSchemeIds.has(item.scheme_id)}
                        />
                      ))}
                    </tbody>
                  </table>
                  {filteredMappings.length === 0 && (
                    <p className="px-5 py-8 text-center text-sm text-parchment-400">
                      No schemes match the current filter.
                    </p>
                  )}
                </div>
              </>
            )}
          </section>

          <section id="unmapped-schemes" className="panel overflow-hidden">
            <div className="border-b border-warm-100/15 px-5 py-4">
              <h2 className="text-base font-semibold text-parchment-100">
                2. Unmapped schemes — apply suggestions in bulk
              </h2>
              <p className="mt-1 max-w-4xl text-xs text-parchment-400">
                These schemes have no benchmark mapping. High-confidence suggestions are shown
                where available. Select schemes and apply a benchmark in bulk.
              </p>
            </div>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[1380px] border-collapse text-left text-sm">
                <thead className="bg-ink-900/80 text-[11px] uppercase tracking-[0.14em] text-parchment-400">
                  <tr>
                    <th className="w-10 px-3 py-3">
                      <input
                        aria-label="Select all unmapped schemes"
                        checked={unmappedAllSelected}
                        className="h-4 w-4 cursor-pointer accent-copper-500"
                        onChange={() =>
                          setUnmappedSelected(
                            unmappedAllSelected ? new Set() : new Set(unmappedSchemeIds)
                          )
                        }
                        type="checkbox"
                      />
                    </th>
                    <th className="px-4 py-3 font-semibold">Scheme</th>
                    <th className="px-4 py-3 text-right font-semibold">Folios</th>
                    <th className="px-4 py-3 font-semibold">Suggested benchmark</th>
                    <th className="px-4 py-3 font-semibold">Confidence</th>
                    <th className="px-4 py-3 font-semibold">Reason</th>
                    <th className="px-4 py-3 font-semibold">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-warm-100/10">
                  {unmappedMappings.length === 0 ? (
                    <tr>
                      <td colSpan={7} className="px-5 py-8 text-center text-sm text-parchment-400">
                        All schemes are mapped.
                      </td>
                    </tr>
                  ) : (
                    unmappedMappings.map((item) => (
                      <tr
                        key={item.scheme_id}
                        className={`align-top transition-colors ${
                          unmappedSelected.has(item.scheme_id)
                            ? "bg-copper-500/[0.07]"
                            : "hover:bg-parchment-50/[0.035]"
                        }`}
                      >
                        <td className="w-10 px-3 py-3">
                          <input
                            aria-label={`Select ${item.scheme_name} for bulk mapping`}
                            checked={unmappedSelected.has(item.scheme_id)}
                            className="h-4 w-4 cursor-pointer accent-copper-500"
                            onChange={() =>
                              setUnmappedSelected((current) =>
                                unmappedSelected.has(item.scheme_id)
                                  ? (() => { const next = new Set(current); next.delete(item.scheme_id); return next; })()
                                  : new Set(current).add(item.scheme_id)
                              )
                            }
                            type="checkbox"
                          />
                        </td>
                        <td className="max-w-[330px] px-4 py-4">
                          <p className="font-medium text-parchment-100">{item.scheme_name}</p>
                          <p className="mt-1 break-words font-mono text-[11px] leading-5 text-parchment-400">
                            {item.normalized_scheme_name}
                          </p>
                        </td>
                        <td className="px-4 py-4 text-right">
                          <p className="tabular-nums text-sm text-parchment-200">
                            {item.folio_count.toLocaleString("en-IN")}
                          </p>
                          <p className="text-[10px] uppercase tracking-[0.1em] text-parchment-500">
                            {item.folio_count === 1 ? "folio" : "folios"}
                          </p>
                        </td>
                        <td className="min-w-[280px] px-4 py-4">
                          {item.suggested_benchmark && item.review_status !== "reviewed" ? (
                            <div className="mt-2 rounded-lg border border-amber-400/25 bg-amber-400/[0.07] px-2.5 py-2">
                              <p className="text-[11px] text-amber-200">
                                Suggested: <strong className="font-semibold">{item.suggested_benchmark}</strong>
                              </p>
                              <p className="mt-0.5 text-[10px] leading-4 text-amber-200/70">
                                {item.suggestion_keyword
                                  ? `Matched “${item.suggestion_keyword}” in the scheme name.`
                                  : `${item.suggestion_source ?? "Automatic suggestion"} from the import.`}
                              </p>
                              {item.suggestion_reason && (
                                <p className="mt-0.5 text-[10px] leading-4 text-amber-200/60">
                                  Reason: {item.suggestion_reason}
                                  {item.suggestion_confidence && (
                                    <span className={`ml-1.5 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium
                                      ${item.suggestion_confidence === 'high' ? 'bg-emerald-400/20 text-emerald-300' :
                                       item.suggestion_confidence === 'medium' ? 'bg-amber-400/20 text-amber-300' :
                                       'bg-rose-400/20 text-rose-300'}`}>
                                    {item.suggestion_confidence.toUpperCase()}
                                  </span>
                                  )}
                                  {item.suggestion_match_type && (
                                    <span className="ml-1.5 text-[9px] text-amber-300/70">
                                      ({item.suggestion_match_type.replace('_', ' ')})
                                    </span>
                                  )}
                                </p>
                              )}
                            </div>
                          ) : (
                            <p className="text-[11px] text-parchment-400">No suggestion available</p>
                          )}
                        </td>
                        <td className="px-4 py-4 text-center">
                          {item.suggestion_confidence && (
                            <span className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium
                              ${item.suggestion_confidence === 'high' ? 'bg-emerald-400/20 text-emerald-300' :
                               item.suggestion_confidence === 'medium' ? 'bg-amber-400/20 text-amber-300' :
                               'bg-rose-400/20 text-rose-300'}`}>
                            {item.suggestion_confidence.toUpperCase()}
                          </span>
                          )}
                        </td>
                        <td className="px-4 py-4 text-[11px] text-parchment-500 max-w-[200px] truncate">
                          {item.suggestion_reason ?? "—"}
                        </td>
                        <td className="px-4 py-4 text-right">
                          {item.suggested_benchmark && item.review_status !== "reviewed" ? (
                            <button
                              className="btn-primary whitespace-nowrap px-3 py-1.5 text-xs"
                              disabled={busy || unmappedSelected.size === 0}
                              onClick={() => void handleUnmappedBulkApply(item.suggested_benchmark!)}
                              type="button"
                            >
                              Apply {item.suggested_benchmark}
                            </button>
                          ) : null}
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
            <div className="flex flex-col gap-3 border-b border-warm-100/15 px-5 py-4 lg:flex-row lg:items-end lg:justify-between">
              <div className="flex flex-wrap items-center gap-3 border-b border-warm-100/15 px-5 py-3 text-xs text-parchment-400 lg:border-0 lg:p-0">
                <span>
                  {unmappedMappings.length} unmapped scheme(s)
                  {unmappedSelected.size > 0 && (
                    <> · {unmappedSelected.size.toLocaleString("en-IN")} selected ·{" "}
                    {unmappedMappings.filter(i => unmappedSelected.has(i.scheme_id)).reduce((sum, i) => sum + i.folio_count, 0).toLocaleString("en-IN")} folios
                    </>
                  )}
                </span>
                <button
                  className="font-medium text-copper-300 hover:text-copper-200 disabled:cursor-not-allowed disabled:text-parchment-600"
                  disabled={busy || unmappedSelected.size === 0}
                  onClick={() => setUnmappedSelected(new Set())}
                  type="button"
                >
                  Clear
                </button>
                <button
                  className="font-medium text-copper-300 hover:text-copper-200 disabled:cursor-not-allowed disabled:text-parchment-600"
                  disabled={busy || unmappedMappings.length === 0}
                  onClick={() =>
                    setUnmappedSelected(new Set(unmappedSchemeIds))
                  }
                  type="button"
                >
                  Select all ({unmappedMappings.length.toLocaleString("en-IN")})
                </button>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
                <SearchableSelect
                  label="Benchmark for selected unmapped schemes"
                  options={mappings?.available_benchmarks ?? []}
                  value={unmappedBulkBenchmark}
                  onChange={setUnmappedBulkBenchmark}
                  placeholder="Benchmark for selected schemes…"
                />
                <button
                  className="btn-primary whitespace-nowrap px-3 py-2 text-xs"
                  disabled={
                    busy || unmappedSelected.size === 0 || !unmappedBulkBenchmark
                  }
                  onClick={() => void handleUnmappedBulkApplyFromDropdown()}
                  title="Apply one benchmark to every selected unmapped scheme and all of their folios"
                  type="button"
                >
                  {busy ? "Applying..." : "Apply to selected"}
                </button>
              </div>
            </div>
          </section>

          <section id="refresh-tri" className="panel overflow-hidden">
            <div className="flex flex-col gap-3 border-b border-warm-100/15 px-5 py-4 lg:flex-row lg:items-end lg:justify-between">
              <div>
                <h2 className="text-base font-semibold text-parchment-100">
                  3. Refresh TRI Data from NSE
                </h2>
                <p className="mt-1 text-xs text-parchment-400">
                  Fetches Total Return Index data from NSE for all mapped benchmarks (last 5 years).
                  Only benchmarks with scheme mappings are queried.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-xs text-parchment-400">
                  {levels?.total_benchmarks ?? 0} benchmark series with TRI data
                  {levels?.total_levels ? (
                    <> · {(levels.total_levels ?? 0).toLocaleString("en-IN")} dated levels</>
                  ) : null}
                  {mappings?.coverage.summary.series_missing_dates ? (
                    <> · {mappings.coverage.summary.series_missing_dates} with gaps</>
                  ) : null}
                </span>
                <button
                  className="btn-primary whitespace-nowrap px-3 py-2 text-xs"
                  disabled={busy}
                  onClick={() => void handleRefreshBenchmarkLevels()}
                  title="Fetch TRI data from NSE for all mapped benchmarks (last 5 years)"
                  type="button"
                >
                  {busy ? "Refreshing TRI..." : "Refresh TRI Data from NSE"}
                </button>
              </div>
            </div>
            <div className="p-5 text-xs text-parchment-400">
              <p className="font-medium text-parchment-200">TRI Data Status</p>
              <p className="mt-2 leading-5">
                {levels?.total_benchmarks === 0
                  ? "No TRI data available. Click \"Refresh TRI Data from NSE\" to fetch the latest data from NSE for all mapped benchmarks."
                  : `${(levels?.total_levels ?? 0).toLocaleString("en-IN")} dated levels across ${levels?.total_benchmarks ?? 0} benchmark series. ${mappings?.coverage.summary.series_missing_dates ?? 0} series have missing dates.`}
              </p>
              <p className="mt-2 leading-5">
                Demo file:{" "}
                <code className="rounded bg-parchment-50/[0.06] px-1 py-0.5 text-parchment-300">
                  samples\benchmark_levels\demo_benchmark_levels.csv
                </code>
              </p>
            </div>
          </section>
        </div>
      )}
    </main>
  );
}

function MappingRow({
  busy,
  item,
  onSave,
  onToggleSelected,
  options,
  selected,
}: {
  busy: boolean;
  item: BenchmarkMappingItem;
  onSave: (item: BenchmarkMappingItem, value: string) => void;
  onToggleSelected: (schemeId: number) => void;
  options: string[];
  selected: boolean;
}) {
  const [editValue, setEditValue] = useState(item.benchmark_name);
  const [isEditing, setIsEditing] = useState(false);

  const handleSave = () => {
    if (editValue.trim() && editValue !== item.benchmark_name) {
      onSave(item, editValue.trim());
    }
    setIsEditing(false);
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSave();
    } else if (e.key === "Escape") {
      setEditValue(item.benchmark_name);
      setIsEditing(false);
    }
  };

  return (
    <tr
      className={`align-top transition-colors ${
        selected ? "bg-copper-500/[0.07]" : "hover:bg-parchment-50/[0.035]"
      }`}
    >
      <td className="w-10 px-3 py-3">
        <input
          aria-label={`Select ${item.scheme_name}`}
          checked={selected}
          className="h-4 w-4 cursor-pointer accent-copper-500"
          onChange={() => onToggleSelected(item.scheme_id)}
          type="checkbox"
        />
      </td>
      <td className="max-w-[330px] px-4 py-4">
        <p className="font-medium text-parchment-100">{item.scheme_name}</p>
        <p className="mt-1 break-words font-mono text-[11px] leading-5 text-parchment-400">
          {item.normalized_scheme_name}
        </p>
      </td>
      <td className="px-4 py-4 text-right">
        <p className="tabular-nums text-sm text-parchment-200">
          {item.folio_count.toLocaleString("en-IN")}
        </p>
        <p className="text-[10px] uppercase tracking-[0.1em] text-parchment-500">
          {item.folio_count === 1 ? "folio" : "folios"}
        </p>
      </td>
      <td className="min-w-[280px] px-4 py-4">
        {isEditing ? (
          <SearchableSelect
            options={options}
            value={editValue}
            onChange={setEditValue}
            placeholder="Search benchmark…"
          />
        ) : (
          <div className="flex items-center gap-2">
            <p className="text-sm text-parchment-100">{item.benchmark_name || "—"}</p>
            {item.suggested_benchmark && item.review_status !== "reviewed" && (
              <button
                className="btn-secondary px-2 py-1 text-[10px]"
                onClick={() => {
                  setEditValue(item.suggested_benchmark!);
                  setIsEditing(true);
                }}
                type="button"
              >
                Use suggestion
              </button>
            )}
            {item.review_status !== "reviewed" && (
              <button
                className="btn-secondary px-2 py-1 text-[10px]"
                onClick={() => setIsEditing(true)}
                type="button"
              >
                Edit
              </button>
            )}
          </div>
        )}
        {item.suggested_benchmark && item.review_status !== "reviewed" && (
          <div className="mt-2 rounded-lg border border-amber-400/25 bg-amber-400/[0.07] px-2.5 py-2">
            <p className="text-[11px] text-amber-200">
              Suggested: <strong className="font-semibold">{item.suggested_benchmark}</strong>
            </p>
            <p className="mt-0.5 text-[10px] leading-4 text-amber-200/70">
              {item.suggestion_keyword
                ? `Matched “${item.suggestion_keyword}” in the scheme name.`
                : `${item.suggestion_source ?? "Automatic suggestion"} from the import.`}
            </p>
            {item.suggestion_reason && (
              <p className="mt-0.5 text-[10px] leading-4 text-amber-200/60">
                Reason: {item.suggestion_reason}
                {item.suggestion_confidence && (
                  <span className={`ml-1.5 inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[9px] font-medium
                    ${item.suggestion_confidence === 'high' ? 'bg-emerald-400/20 text-emerald-300' :
                     item.suggestion_confidence === 'medium' ? 'bg-amber-400/20 text-amber-300' :
                     'bg-rose-400/20 text-rose-300'}`}>
                  {item.suggestion_confidence.toUpperCase()}
                </span>
                )}
                {item.suggestion_match_type && (
                  <span className="ml-1.5 text-[9px] text-amber-300/70">
                    ({item.suggestion_match_type.replace('_', ' ')})
                  </span>
                )}
              </p>
            )}
          </div>
        )}
      </td>
      <td className="px-4 py-4">
        <MappingStatusBadge item={item} />
      </td>
      <td className="px-4 py-4 text-right">
        {item.review_status !== "reviewed" && isEditing && (
          <button
            className="btn-primary whitespace-nowrap px-3 py-1.5 text-xs"
            disabled={busy}
            onClick={handleSave}
            type="button"
          >
            Save
          </button>
        )}
        {item.review_status !== "reviewed" && !isEditing && (
          <button
            className="btn-secondary whitespace-nowrap px-3 py-1.5 text-xs"
            disabled={busy}
            onClick={() => setIsEditing(true)}
            type="button"
          >
            Edit
          </button>
        )}
      </td>
    </tr>
  );
}