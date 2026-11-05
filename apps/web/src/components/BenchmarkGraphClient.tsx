"use client";

import Link from "next/link";
import {
  useCallback,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import AppNav from "@/components/AppNav";
import BenchmarkGraph, {
  type BenchmarkGraphHandle,
} from "@/components/BenchmarkGraph";
import BenchmarkGraphInspector from "@/components/BenchmarkGraphInspector";
import FolioDetailDialog from "@/components/FolioDetailDialog";
import { api } from "@/lib/api";
import { formatDate } from "@/lib/format";
import { SearchableSelect } from "@/components/SearchableSelect";
import {
  fullscreenWorkspaceClass,
  nextFullscreenState,
} from "@/lib/fullscreen";
import { buildGraphLayout } from "@/lib/graphLayout";
import type {
  BenchmarkGraphCluster,
  BenchmarkGraphFolio,
  BenchmarkGraphResponse,
  GraphPerformance,
} from "@/lib/types";

type PerformanceFilter =
  | "all"
  | Extract<GraphPerformance, "ahead" | "behind" | "not_available" | "needs_review">;

function SummaryCard({
  label,
  value,
  note,
  tone = "text-parchment-50",
  onClick,
  active = false,
}: {
  label: string;
  value: string | number;
  note?: string;
  tone?: string;
  onClick?: () => void;
  active?: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`glass-panel relative overflow-hidden px-4 py-3.5 transition-colors ${
        onClick
          ? "cursor-pointer hover:border-copper-400/30 hover:bg-parchment-50/10"
          : ""
      } ${active ? "ring-2 ring-copper-400/50" : ""}`}
      aria-pressed={active}
    >
      <span
        aria-hidden
        className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-copper-400/45 via-copper-400/10 to-transparent"
      />
      <p className="eyebrow">{label}</p>
      <p className={`mt-1.5 text-2xl font-semibold tracking-tight ${tone}`}>
        {typeof value === "number" ? value.toLocaleString("en-IN") : value}
      </p>
      {note && <p className="mt-0.5 text-[10px] text-parchment-400">{note}</p>}
    </button>
  );
}

function LegendDot({ className, label }: { className: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1.5 text-[11px] text-parchment-400">
      <span className={`h-2.5 w-2.5 rounded-full ${className}`} />
      {label}
    </span>
  );
}

function clientKey(folio: BenchmarkGraphFolio): string {
  return folio.client_id === null ? "unmatched" : String(folio.client_id);
}

export default function BenchmarkGraphClient() {
  const [data, setData] = useState<BenchmarkGraphResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const deferredQuery = useDeferredValue(query);
  const [performanceFilter, setPerformanceFilter] =
    useState<PerformanceFilter>("all");
  const [benchmarkFilter, setBenchmarkFilter] = useState("all");
  const [clientFilter, setClientFilter] = useState("all");
  const [selectedClusterId, setSelectedClusterId] = useState<string | null>(
    null,
  );
  const [selectedFolioId, setSelectedFolioId] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const graphRef = useRef<BenchmarkGraphHandle | null>(null);
  const workspaceRef = useRef<HTMLDivElement | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const payload = await api.benchmarkGraph();
      setData(payload);
      setError(null);
    } catch (err) {
      setError(
        err instanceof Error
          ? `${err.message}. Make sure the local API is running at ${api.baseUrl}.`
          : "Could not load the benchmark graph.",
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useEffect(() => {
    function handleFullscreenChange() {
      setIsFullscreen(document.fullscreenElement === workspaceRef.current);
    }
    document.addEventListener("fullscreenchange", handleFullscreenChange);
    return () =>
      document.removeEventListener("fullscreenchange", handleFullscreenChange);
  }, []);

  useEffect(() => {
    if (!isFullscreen) return;
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key !== "Escape") return;
      if (document.fullscreenElement) {
        void document.exitFullscreen().catch(() => undefined);
      }
      setIsFullscreen(false);
    }
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [isFullscreen]);

  const toggleFullscreen = useCallback(async () => {
    const target = workspaceRef.current;
    const next = nextFullscreenState(isFullscreen, "toggle");
    setIsFullscreen(next);
    if (!target) return;
    try {
      if (next) {
        if (target.requestFullscreen) await target.requestFullscreen();
      } else if (document.fullscreenElement) {
        await document.exitFullscreen();
      }
    } catch {
      // The fixed workspace class is the fallback when the browser refuses
      // or does not support the Fullscreen API.
    }
  }, [isFullscreen]);

  const clusters = useMemo<BenchmarkGraphCluster[]>(
    () => data?.clusters ?? [],
    [data],
  );
  const layout = useMemo(() => buildGraphLayout(clusters), [clusters]);
  const allFolios = useMemo(
    () => clusters.flatMap((cluster) => cluster.folios),
    [clusters],
  );
  const folioById = useMemo(() => {
    const result = new Map<string, BenchmarkGraphFolio>();
    for (const folio of allFolios) result.set(folio.id, folio);
    return result;
  }, [allFolios]);

  const clientOptions = useMemo(() => {
    const grouped = new Map<
      string,
      { key: string; name: string; count: number }
    >();
    for (const folio of allFolios) {
      const key = clientKey(folio);
      const existing = grouped.get(key);
      if (existing) {
        existing.count += 1;
      } else {
        grouped.set(key, {
          key,
          name:
            folio.client_id === null
              ? "Unmatched client"
              : folio.client_name,
          count: 1,
        });
      }
    }
    return [...grouped.values()].sort((left, right) =>
      left.name.localeCompare(right.name),
    );
  }, [allFolios]);

  const visibleClusterIds = useMemo(() => {
    if (benchmarkFilter !== "all") return new Set([benchmarkFilter]);
    return new Set(clusters.map((cluster) => cluster.id));
  }, [benchmarkFilter, clusters]);

  const visibleFolioIds = useMemo(() => {
    const visible = new Set<string>();
    for (const cluster of clusters) {
      if (!visibleClusterIds.has(cluster.id)) continue;
      for (const folio of cluster.folios) {
        if (
          performanceFilter !== "all" &&
          folio.performance !== performanceFilter
        ) {
          continue;
        }
        if (clientFilter !== "all" && clientKey(folio) !== clientFilter) {
          continue;
        }
        visible.add(folio.id);
      }
    }
    return visible;
  }, [
    clientFilter,
    clusters,
    performanceFilter,
    visibleClusterIds,
  ]);

  const filterKey = `${performanceFilter}|${clientFilter}|${benchmarkFilter}`;
  const search = deferredQuery.trim().toLowerCase();
  const searchActive = search.length > 0;

  const matchedFolioIds = useMemo(() => {
    const matched = new Set<string>();
    if (!searchActive) return matched;
    for (const cluster of clusters) {
      if (!visibleClusterIds.has(cluster.id)) continue;
      const clusterMatches = cluster.name.toLowerCase().includes(search);
      for (const folio of cluster.folios) {
        if (!visibleFolioIds.has(folio.id)) continue;
        if (
          clusterMatches ||
          folio.client_name.toLowerCase().includes(search) ||
          folio.folio_number.toLowerCase().includes(search) ||
          folio.scheme_name.toLowerCase().includes(search) ||
          folio.benchmark_name.toLowerCase().includes(search)
        ) {
          matched.add(folio.id);
        }
      }
    }
    return matched;
  }, [clusters, search, searchActive, visibleClusterIds, visibleFolioIds]);

  const matchedClusterIds = useMemo(() => {
    const matched = new Set<string>();
    if (!searchActive) return matched;
    for (const cluster of clusters) {
      if (!visibleClusterIds.has(cluster.id)) continue;
      const clusterMatches = cluster.name.toLowerCase().includes(search);
      const folioMatches = cluster.folios.some(
        (folio) => visibleFolioIds.has(folio.id) && matchedFolioIds.has(folio.id),
      );
      if (clusterMatches || folioMatches) matched.add(cluster.id);
    }
    return matched;
  }, [
    clusters,
    matchedFolioIds,
    search,
    searchActive,
    visibleClusterIds,
    visibleFolioIds,
  ]);

  const matchCount = matchedFolioIds.size + matchedClusterIds.size;
  const searchKey = `${search}|${filterKey}|${matchCount}`;
  const filtersActive =
    performanceFilter !== "all" ||
    benchmarkFilter !== "all" ||
    clientFilter !== "all";

  const selectedCluster = useMemo(
    () =>
      clusters.find((cluster) => cluster.id === selectedClusterId) ?? null,
    [clusters, selectedClusterId],
  );
  const selectedFolio = selectedFolioId
    ? folioById.get(selectedFolioId) ?? null
    : null;

  useEffect(() => {
    if (selectedClusterId && !visibleClusterIds.has(selectedClusterId)) {
      setSelectedClusterId(null);
    }
  }, [selectedClusterId, visibleClusterIds]);

  const visibleFolioCount = visibleFolioIds.size;
  const hasData = data?.meta.has_data ?? false;

  function clearFilters() {
    setPerformanceFilter("all");
    setClientFilter("all");
    setBenchmarkFilter("all");
  }

  const showEmptyGraph =
    !loading && data !== null && visibleClusterIds.size === 0;

  return (
    <main className="mx-auto w-full max-w-[1700px] px-4 py-6 sm:px-6 lg:px-8">
      <header className="mb-6">
        <div className="mb-3">
          <AppNav active="graph" />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-2xl font-semibold tracking-tight text-parchment-50 sm:text-3xl">
            Benchmark Cluster Graph
          </h1>
          <span className="rounded-full bg-sage-500/10 px-2.5 py-1 text-[11px] font-semibold text-sage-300 ring-1 ring-inset ring-sage-500/25">
            Local only
          </span>
          {data?.meta.valuation_date && (
            <span className="rounded-full bg-copper-400/10 px-2.5 py-1 text-[11px] font-semibold text-copper-300 ring-1 ring-inset ring-copper-400/25">
              Valuation {formatDate(data.meta.valuation_date)}
            </span>
          )}
        </div>
        <p className="mt-2 max-w-3xl text-sm leading-5 text-parchment-400">
          A clustered view of every locally mapped benchmark and its folios.
          Client names stay primary, scheme names appear as you zoom, and node
          colours use the existing benchmark comparison results.
        </p>
      </header>

      {error && (
        <div className="mb-4 rounded-xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-200">
          {error}
        </div>
      )}

      {!hasData && !loading && (
        <div className="mb-4 flex flex-col gap-2 rounded-xl border border-amber-400/25 bg-amber-400/[0.07] px-4 py-3 text-sm text-amber-200 sm:flex-row sm:items-center sm:justify-between">
          <p>
            No folio snapshot is loaded. The benchmark nuclei still appear with
            zero folios so empty categories remain visible.
          </p>
          <Link className="btn-secondary shrink-0 px-3 py-1.5 text-xs" href="/">
            Open Upload
          </Link>
        </div>
      )}

      {loading && !data ? (
        <div className="panel p-10 text-center text-sm text-parchment-400">
          Loading local benchmark graph…
        </div>
      ) : (
        <>
          <div className="mb-4 grid grid-cols-2 gap-2.5 sm:grid-cols-3 xl:grid-cols-6">
            <SummaryCard
              label="Benchmarks"
              value={data?.summary.benchmarks ?? 0}
              note="Nuclei in the graph"
            />
            <SummaryCard
              label="Folios"
              value={data?.summary.folios ?? 0}
              note={`${visibleFolioCount.toLocaleString("en-IN")} shown by filters`}
            />
            <SummaryCard
              label="Ahead"
              value={data?.summary.ahead ?? 0}
              note="Green nodes"
              tone="text-emerald-300"
              onClick={() => setPerformanceFilter(performanceFilter === "ahead" ? "all" : "ahead")}
              active={performanceFilter === "ahead"}
            />
            <SummaryCard
              label="Behind"
              value={data?.summary.behind ?? 0}
              note="Red nodes"
              tone="text-rose-300"
              onClick={() => setPerformanceFilter(performanceFilter === "behind" ? "all" : "behind")}
              active={performanceFilter === "behind"}
            />
            <SummaryCard
              label="Not available"
              value={data?.summary.not_available ?? 0}
              note="Grey comparison gaps"
              tone="text-parchment-300"
              onClick={() => setPerformanceFilter(performanceFilter === "not_available" ? "all" : "not_available")}
              active={performanceFilter === "not_available"}
            />
            <SummaryCard
              label="Needs review"
              value={data?.summary.needs_review ?? 0}
              note="Amber mapping or data"
              tone="text-amber-300"
              onClick={() => setPerformanceFilter(performanceFilter === "needs_review" ? "all" : "needs_review")}
              active={performanceFilter === "needs_review"}
            />
          </div>

          <section className="panel mb-4 px-4 py-3 text-xs text-parchment-400">
            <div className="flex flex-wrap items-center gap-x-5 gap-y-2">
              <span className="font-semibold uppercase tracking-[0.14em] text-parchment-500">
                How to read the graph
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
                Green = Ahead of benchmark
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-rose-500" />
                Red = Behind benchmark
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-[#8a8178]" />
                Grey = Not available: no dated transactions, missing current
                value, or a return that cannot be calculated
              </span>
              <span className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full bg-amber-500" />
                Amber = Needs review: mapping missing/unapproved or local
                benchmark dates missing
              </span>
            </div>
            <p className="mt-2 leading-5">
              Select a folio to see the exact reason. Missing benchmark levels
              stay Not available and are never estimated. Add the missing dates
              on Benchmark Data, or approve the mapping, then return here.
            </p>
          </section>

          <div
            className={fullscreenWorkspaceClass(isFullscreen)}
            data-graph-fullscreen={isFullscreen ? "true" : "false"}
            ref={workspaceRef}
          >
            {isFullscreen && (
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-warm-100/15 bg-ink-900/95 px-4 py-2.5">
                <div>
                  <p className="text-sm font-semibold text-parchment-100">
                    Benchmark Cluster Graph
                  </p>
                  <p className="text-[11px] text-parchment-400">
                    Fullscreen view · press Esc or use Exit fullscreen to return.
                  </p>
                </div>
                <button
                  className="btn-secondary px-3 py-1.5 text-xs"
                  onClick={() => void toggleFullscreen()}
                  type="button"
                >
                  Exit fullscreen
                </button>
              </div>
            )}
          <section className="panel mb-4 p-4">
            <div className="flex flex-col gap-3">
              <div className="flex flex-col gap-3 lg:flex-row lg:items-end">
                <label className="block min-w-0 flex-1">
                  <span className="eyebrow">Search the graph</span>
                  <input
                    aria-label="Search client, folio, scheme or benchmark"
                    className="field mt-1.5 w-full px-3.5 py-2.5 text-sm"
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search client, folio, scheme or benchmark…"
                    type="search"
                    value={query}
                  />
                </label>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                  <label className="block">
                    <span className="eyebrow">Performance</span>
                    <select
                      aria-label="Filter by performance"
                      className="field mt-1.5 w-full px-3 py-2.5 text-sm"
                      onChange={(event) =>
                        setPerformanceFilter(
                          event.target.value as PerformanceFilter,
                        )
                      }
                      value={performanceFilter}
                    >
                      <option value="all">Show all folios</option>
                      <option value="ahead">Only outperforming</option>
                      <option value="behind">Only underperforming</option>
                      <option value="not_available">Only not available</option>
                      <option value="needs_review">Only needs review</option>
                    </select>
                  </label>
                  <label className="block">
                    <span className="eyebrow">Benchmark</span>
                    <SearchableSelect
                      options={["all", ...clusters.map((cluster) => cluster.id)]}
                      value={benchmarkFilter}
                      onChange={setBenchmarkFilter}
                      placeholder="All benchmarks"
                    />
                  </label>
                  <label className="block">
                    <span className="eyebrow">Client</span>
                    <SearchableSelect
                      options={["all", ...clientOptions.map((client) => client.key)]}
                      value={clientFilter}
                      onChange={setClientFilter}
                      placeholder="All clients"
                    />
                  </label>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 border-t border-warm-100/10 pt-3 text-xs text-parchment-400">
                <span>
                  Showing{" "}
                  <strong className="font-medium text-parchment-200">
                    {visibleFolioCount.toLocaleString("en-IN")}
                  </strong>{" "}
                  of{" "}
                  <strong className="font-medium text-parchment-200">
                    {(data?.summary.folios ?? 0).toLocaleString("en-IN")}
                  </strong>{" "}
                  folios
                </span>
                {searchActive && (
                  <>
                    <span className="text-parchment-600">·</span>
                    <span>
                      {matchCount > 0
                        ? `${matchCount} matching node${matchCount === 1 ? "" : "s"} highlighted`
                        : "No matching nodes"}
                    </span>
                  </>
                )}
                <span className="text-parchment-600">·</span>
                <button
                  className="font-medium text-copper-300 hover:text-copper-200 disabled:cursor-not-allowed disabled:text-parchment-500 disabled:hover:text-parchment-500"
                  disabled={!searchActive || matchCount === 0}
                  onClick={() => graphRef.current?.focusMatches()}
                  title={
                    !searchActive
                      ? "Enter a search term to focus matching nodes"
                      : matchCount === 0
                        ? "No matching nodes to focus"
                        : "Zoom to the matching nodes"
                  }
                  type="button"
                >
                  Focus matches
                </button>
                <button
                  className="font-medium text-copper-300 hover:text-copper-200"
                  onClick={() => graphRef.current?.fitToScreen()}
                  type="button"
                >
                  Fit to screen
                </button>
                <button
                  className="font-medium text-copper-300 hover:text-copper-200"
                  onClick={() => graphRef.current?.resetView()}
                  type="button"
                >
                  Reset view
                </button>
                <button
                  aria-pressed={isFullscreen}
                  className="font-semibold text-copper-300 hover:text-copper-200"
                  onClick={() => void toggleFullscreen()}
                  title={
                    isFullscreen
                      ? "Exit fullscreen and return to the page"
                      : "Show the graph, search and filters in fullscreen"
                  }
                  type="button"
                >
                  {isFullscreen ? "Exit fullscreen" : "Fullscreen"}
                </button>
                <button
                  className="font-medium text-copper-300 hover:text-copper-200 disabled:cursor-not-allowed disabled:text-parchment-500 disabled:hover:text-parchment-500"
                  disabled={!filtersActive}
                  onClick={clearFilters}
                  title={
                    filtersActive
                      ? "Reset performance, benchmark and client filters"
                      : "No filters are active"
                  }
                  type="button"
                >
                  Clear filters
                </button>
                {filtersActive && (
                  <span className="rounded-full border border-copper-400/20 bg-copper-400/10 px-2 py-0.5 text-[10px] font-medium text-copper-200">
                    Filters active
                  </span>
                )}
              </div>
            </div>
          </section>

          <div
            className={
              isFullscreen
                ? "grid gap-4"
                : "grid gap-4 xl:grid-cols-[minmax(0,1fr)_390px]"
            }
          >
            <div className="min-w-0">
              {showEmptyGraph ? (
                <div className="panel flex min-h-[680px] flex-col items-center justify-center gap-3 p-10 text-center">
                  <span className="flex h-11 w-11 items-center justify-center rounded-full bg-amber-400/10 text-lg text-amber-300 ring-1 ring-inset ring-amber-400/25">
                    !
                  </span>
                  <h2 className="text-base font-semibold text-parchment-100">
                    No benchmarks match this filter
                  </h2>
                  <p className="max-w-sm text-sm leading-6 text-parchment-400">
                    Clear the benchmark filter to bring every cluster back into
                    view. Folio filters never remove the benchmark nuclei.
                  </p>
                  <button
                    className="btn-secondary mt-1 px-3 py-1.5 text-xs"
                    onClick={clearFilters}
                    type="button"
                  >
                    Clear filters
                  </button>
                </div>
              ) : (
                <BenchmarkGraph
                  clusters={clusters}
                  filterKey={filterKey}
                  fullscreen={isFullscreen}
                  layout={layout}
                  matchCount={matchCount}
                  matchedClusterIds={matchedClusterIds}
                  matchedFolioIds={matchedFolioIds}
                  onClearSelection={() => {
                    setSelectedClusterId(null);
                    setSelectedFolioId(null);
                  }}
                  onSelectCluster={(clusterId) => {
                    setSelectedClusterId(clusterId);
                    setSelectedFolioId(null);
                  }}
                  onSelectFolio={(folioId) => {
                    setSelectedFolioId(folioId);
                  }}
                  onToggleFullscreen={() => void toggleFullscreen()}
                  ref={graphRef}
                  searchActive={searchActive}
                  searchKey={searchKey}
                  selectedClusterId={selectedClusterId}
                  selectedFolioId={selectedFolioId}
                  visibleClusterIds={visibleClusterIds}
                  visibleFolioIds={visibleFolioIds}
                />
              )}
              <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1.5 px-1">
                <LegendDot
                  className="bg-[#433229] ring-2 ring-copper-400/50"
                  label="Benchmark nucleus"
                />
                <LegendDot className="bg-emerald-400" label="Ahead" />
                <LegendDot className="bg-rose-400" label="Behind" />
                <LegendDot className="bg-parchment-400" label="Not available" />
                <LegendDot className="bg-amber-400" label="Needs review" />
                <span className="ml-auto text-[10px] text-parchment-500">
                  {layout.folios.length > 0
                    ? "Client names at standard zoom · scheme names when closer · hover for full detail."
                    : "No folio nodes to label."}
                </span>
              </div>
            </div>

            {!isFullscreen && (
              <BenchmarkGraphInspector
                cluster={selectedCluster}
                onFocusCluster={(clusterId) =>
                  graphRef.current?.focusCluster(clusterId)
                }
                onSelectFolio={(folioId) => setSelectedFolioId(folioId)}
              />
            )}
          </div>

          <FolioDetailDialog
            folio={selectedFolio}
            onClose={() => setSelectedFolioId(null)}
          />
          </div>

          <footer className="mt-6 flex flex-col gap-2 border-t border-warm-100/15 pt-4 text-xs text-parchment-400 sm:flex-row sm:items-center sm:justify-between">
            <p>
              Graph nodes are grouped from reviewed benchmark mappings and
              existing folio comparison results. Missing mappings, levels or folio
              AUM are shown as review or unavailable states, never repaired.
            </p>
            <p>
              Benchmark data:{" "}
              <span className="text-parchment-300">
                {data?.meta.benchmark_data ?? "Not available"}
              </span>
            </p>
          </footer>
        </>
      )}

    </main>
  );
}
