"use client";

import Badge from "@/components/Badge";
import { formatPercent } from "@/lib/format";
import type { BenchmarkGraphCluster } from "@/lib/types";

function reviewBadge(cluster: BenchmarkGraphCluster) {
  if (cluster.review_state === "needs_mapping") {
    return <Badge tone="amber">Needs mapping</Badge>;
  }
  if (cluster.review_state === "needs_review") {
    return <Badge tone="amber">Needs review</Badge>;
  }
  if (cluster.review_state === "levels_missing") {
    return <Badge tone="amber">Levels missing</Badge>;
  }
  if (cluster.review_state === "ready") {
    return <Badge tone="blue">Comparisons ready</Badge>;
  }
  if (cluster.review_state === "partial") {
    return <Badge tone="blue">Partial comparison</Badge>;
  }
  if (cluster.review_state === "no_folios") {
    return <Badge tone="slate">No folios</Badge>;
  }
  return <Badge tone="slate">Not available</Badge>;
}

function Stat({
  label,
  value,
  tone = "text-parchment-100",
}: {
  label: string;
  value: string | number;
  tone?: string;
}) {
  return (
    <div className="panel-muted px-3 py-2.5">
      <p className="text-[10px] font-medium uppercase tracking-[0.12em] text-parchment-500">
        {label}
      </p>
      <p className={`mt-1 text-lg font-semibold tabular-nums ${tone}`}>{value}</p>
    </div>
  );
}

export default function BenchmarkGraphInspector({
  cluster,
  onFocusCluster,
  onSelectFolio,
}: {
  cluster: BenchmarkGraphCluster | null;
  onFocusCluster: (clusterId: string) => void;
  onSelectFolio: (folioId: string) => void;
}) {
  if (!cluster) {
    return (
      <aside className="glass-inspector flex h-full min-h-[680px] flex-col p-5">
        <p className="eyebrow">Graph guide</p>
        <h2 className="mt-2 text-base font-semibold text-parchment-100">
          How to read the cluster graph
        </h2>
        <p className="mt-2 text-xs leading-5 text-parchment-400">
          Each dark bronze nucleus is a benchmark category. Smaller nodes are
          the folios mapped to it. Hover any node for a full business summary,
          click a nucleus for cluster statistics, or click a folio for the shared
          detail popup.
        </p>

        <div className="mt-5 space-y-3">
          <div className="flex items-center gap-3">
            <span className="h-4 w-4 shrink-0 rounded-full bg-[#433229] ring-2 ring-copper-400/50" />
            <p className="text-xs text-parchment-300">
              Benchmark nucleus — folio count and status summary below it
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="h-3 w-3 shrink-0 rounded-full bg-emerald-400" />
            <p className="text-xs text-parchment-300">Folio ahead of benchmark</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="h-3 w-3 shrink-0 rounded-full bg-rose-400" />
            <p className="text-xs text-parchment-300">Folio behind benchmark</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="h-3 w-3 shrink-0 rounded-full bg-parchment-400" />
            <p className="text-xs text-parchment-300">
              Comparison not available (grey)
            </p>
          </div>
          <div className="flex items-center gap-3">
            <span className="h-3 w-3 shrink-0 rounded-full bg-amber-400" />
            <p className="text-xs text-parchment-300">
              Mapping or benchmark data needs review (amber)
            </p>
          </div>
        </div>

        <div className="mt-5 rounded-xl border border-copper-400/15 bg-copper-400/[0.05] px-4 py-3 text-xs leading-5 text-parchment-300">
          <p className="font-medium text-copper-200">Labels and navigation</p>
          <p className="mt-1">
            Folio labels show the client name, then the scheme name as you zoom
            closer. Hovering a node always reveals the full client, folio,
            scheme, value, return and benchmark comparison.
          </p>
          <p className="mt-2">
            Drag to pan. Scroll or use{" "}
            <span className="font-semibold">+</span> /{" "}
            <span className="font-semibold">−</span> to zoom; the coordinate grid
            moves and rescales with the graph.{" "}
            <span className="font-semibold">FIT</span> fits all clusters;{" "}
            <span className="font-semibold">RESET</span> clears the selection and
            restores the fitted view.
          </p>
        </div>
        <div className="mt-4 rounded-xl border border-warm-100/15 bg-parchment-50/[0.03] px-4 py-3 text-xs leading-5 text-parchment-400">
          Search highlights matching nodes without hiding the rest. Filters
          change which folios are drawn, but benchmark nuclei stay visible so
          empty categories remain identifiable.
        </div>
      </aside>
    );
  }

  const stats = cluster.stats;
  const averageTone =
    stats.average_difference === null
      ? "text-parchment-300"
      : stats.average_difference > 0
        ? "text-emerald-300"
        : stats.average_difference < 0
          ? "text-rose-300"
          : "text-parchment-200";
  const pointToPoint = cluster.folios.filter(
    (folio) => folio.benchmark_comparison_method === "point_to_point",
  ).length;
  const cashFlow = cluster.folios.filter(
    (folio) => folio.benchmark_comparison_method === "cash_flow_xirr",
  ).length;

  return (
    <aside className="glass-inspector flex h-full min-h-[680px] flex-col p-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="eyebrow">Benchmark summary</p>
          <h2 className="mt-2 text-lg font-semibold tracking-tight text-parchment-50">
            {cluster.name}
          </h2>
          <div className="mt-2">{reviewBadge(cluster)}</div>
        </div>
        <button
          className="btn-secondary shrink-0 px-3 py-1.5 text-xs"
          onClick={() => onFocusCluster(cluster.id)}
          type="button"
        >
          Focus
        </button>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <Stat label="Folios" value={stats.folio_count} />
        <Stat label="Ahead" value={stats.ahead} tone="text-emerald-300" />
        <Stat label="Behind" value={stats.behind} tone="text-rose-300" />
        <Stat label="Not available" value={stats.not_available} />
        <Stat
          label="Needs review"
          value={stats.needs_review}
          tone="text-amber-300"
        />
        <Stat label="Missing AUM" value={stats.missing_folio_aum} />
      </div>

      <div className="mt-4 rounded-xl border border-warm-100/15 bg-parchment-50/[0.035] px-4 py-3">
        <p className="eyebrow">Average folio performance</p>
        <p className={`mt-1 text-2xl font-semibold tabular-nums ${averageTone}`}>
          {formatPercent(stats.average_difference)}
        </p>
        <p className="mt-1 text-[11px] leading-5 text-parchment-400">
          Average difference across{" "}
          {stats.available.toLocaleString("en-IN")} comparable folio
          {stats.available === 1 ? "" : "s"}. Positive means the folio is ahead
          of its benchmark.
        </p>
        <div className="mt-3 grid grid-cols-2 gap-2 text-[11px]">
          <div className="rounded-lg bg-parchment-50/[0.045] px-2.5 py-2">
            <p className="text-parchment-500">Average folio</p>
            <p className="mt-0.5 font-medium text-parchment-200">
              {formatPercent(stats.average_folio_return)}
            </p>
          </div>
          <div className="rounded-lg bg-parchment-50/[0.045] px-2.5 py-2">
            <p className="text-parchment-500">Average benchmark</p>
            <p className="mt-0.5 font-medium text-parchment-200">
              {formatPercent(stats.average_benchmark_return)}
            </p>
          </div>
        </div>
      </div>

      <div className="mt-4 space-y-2 text-xs text-parchment-400">
        <div className="flex items-center justify-between gap-3">
          <span>Local benchmark levels</span>
          <span className="font-medium text-parchment-200">
            {cluster.level_count.toLocaleString("en-IN")}
          </span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span>Point-to-point comparisons</span>
          <span className="font-medium text-parchment-200">{pointToPoint}</span>
        </div>
        <div className="flex items-center justify-between gap-3">
          <span>Cash-flow XIRR comparisons</span>
          <span className="font-medium text-parchment-200">{cashFlow}</span>
        </div>
      </div>

      {stats.folio_count === 0 ? (
        <div className="mt-4 rounded-xl border border-warm-100/15 bg-parchment-50/[0.03] px-4 py-3 text-xs leading-5 text-parchment-400">
          No folios are mapped to this benchmark yet. The nucleus remains
          visible so you can see the category in the business view.
        </div>
      ) : (
        <div className="mt-4 min-h-0 flex-1">
          <div className="flex items-center justify-between">
            <p className="eyebrow">Folios in this cluster</p>
            <span className="text-[10px] text-parchment-500">
              click to open detail
            </span>
          </div>
          <div className="mt-2 max-h-[190px] space-y-1.5 overflow-y-auto pr-1">
            {cluster.folios.map((folio) => (
              <button
                className="flex w-full items-center justify-between gap-3 rounded-lg border border-warm-100/10 bg-parchment-50/[0.03] px-3 py-2 text-left transition-colors hover:bg-parchment-50/[0.07]"
                key={folio.id}
                onClick={() => onSelectFolio(folio.id)}
                type="button"
              >
                <span className="min-w-0">
                  <span className="flex items-center gap-2">
                    <span
                      className={`h-2 w-2 shrink-0 rounded-full ${
                        folio.performance === "ahead"
                          ? "bg-emerald-400"
                          : folio.performance === "behind"
                            ? "bg-rose-400"
                            : folio.performance === "needs_review"
                              ? "bg-amber-400"
                              : "bg-parchment-400"
                      }`}
                    />
                    <span className="font-mono text-[11px] text-copper-300">
                      {folio.folio_number}
                    </span>
                    <span className="truncate text-[11px] text-parchment-300">
                      {folio.client_name}
                    </span>
                  </span>
                  <span className="mt-0.5 block truncate pl-4 text-[10px] text-parchment-500">
                    {folio.scheme_name}
                  </span>
                </span>
                <span
                  className={`shrink-0 text-[11px] font-semibold tabular-nums ${
                    folio.benchmark_difference === null
                      ? "text-parchment-400"
                      : folio.benchmark_difference > 0
                        ? "text-emerald-300"
                        : folio.benchmark_difference < 0
                          ? "text-rose-300"
                          : "text-parchment-300"
                  }`}
                >
                  {formatPercent(folio.benchmark_difference)}
                </span>
              </button>
            ))}
          </div>
        </div>
      )}
    </aside>
  );
}
