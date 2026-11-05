"use client";

import {
  forwardRef,
  useCallback,
  useEffect,
  useImperativeHandle,
  useMemo,
  useRef,
  useState,
  type MouseEvent as ReactMouseEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import type {
  BenchmarkGraphCluster,
  BenchmarkGraphFolio,
  GraphPerformance,
} from "@/lib/types";
import type {
  GraphBounds,
  GraphLayout,
  PositionedCluster,
  PositionedFolio,
} from "@/lib/graphLayout";
import { formatCurrency, formatPercent, performanceLabel } from "@/lib/format";
import { graphCanvasClass } from "@/lib/fullscreen";

const COLORS: Record<
  GraphPerformance,
  { fill: string; stroke: string }
> = {
  ahead: { fill: "#236c4f", stroke: "#d5ecdf" },
  behind: { fill: "#a8424e", stroke: "#f2d6d9" },
  in_line: { fill: "#6f665c", stroke: "#f5ede3" },
  not_available: { fill: "#8a8178", stroke: "#f3ece5" },
  needs_review: { fill: "#b67a24", stroke: "#f6e5c4" },
};

const GRAPH_LINK_COLOR = "#8a7463";

const STATUS_PILL: Record<GraphPerformance, string> = {
  ahead: "bg-emerald-400/10 text-emerald-300 ring-emerald-400/25",
  behind: "bg-rose-400/10 text-rose-300 ring-rose-400/25",
  in_line: "bg-parchment-50/[0.06] text-parchment-300 ring-warm-100/15",
  not_available: "bg-parchment-400/10 text-parchment-300 ring-parchment-400/20",
  needs_review: "bg-amber-400/10 text-amber-300 ring-amber-400/25",
};

type LabelTier = "focus" | "primary" | "full";

interface LabelBox {
  left: number;
  top: number;
  right: number;
  bottom: number;
}

interface RenderFolioLabel {
  id: string;
  anchor: "start" | "end" | "middle";
  x: number;
  primary: string;
  secondary: string | null;
  primaryY: number;
  secondaryY: number | null;
  width: number;
  height: number;
  boxLeft: number;
  boxTop: number;
  emphasis: boolean;
}

export interface BenchmarkGraphHandle {
  resetView: () => void;
  fitToScreen: () => void;
  focusCluster: (clusterId: string) => void;
  focusMatches: () => void;
  zoomIn: () => void;
  zoomOut: () => void;
}

interface HoverState {
  kind: "cluster" | "folio";
  id: string;
  x: number;
  y: number;
}

interface Props {
  layout: GraphLayout;
  clusters: BenchmarkGraphCluster[];
  visibleClusterIds: Set<string>;
  visibleFolioIds: Set<string>;
  matchedClusterIds: Set<string>;
  matchedFolioIds: Set<string>;
  matchCount: number;
  searchActive: boolean;
  filterKey: string;
  searchKey: string;
  selectedClusterId: string | null;
  selectedFolioId: string | null;
  onSelectCluster: (clusterId: string) => void;
  onSelectFolio: (folioId: string) => void;
  onClearSelection: () => void;
  fullscreen?: boolean;
  onToggleFullscreen?: () => void;
}

interface PlotArea {
  left: number;
  right: number;
  top: number;
  bottom: number;
  width: number;
  height: number;
  centerX: number;
  centerY: number;
}

interface AxisTick {
  value: number;
  screen: number;
}

interface CoordinateGrid {
  majorStep: number;
  xMajor: AxisTick[];
  xMinor: AxisTick[];
  yMajor: AxisTick[];
  yMinor: AxisTick[];
}

function clamp(value: number, minimum: number, maximum: number): number {
  return Math.min(maximum, Math.max(minimum, value));
}

function plotAreaFor(width: number, height: number): PlotArea {
  const compact = width < 560;
  const left = compact ? 38 : 50;
  const right = Math.max(left + 1, width - (compact ? 12 : 18));
  const top = 16;
  const bottom = Math.max(top + 1, height - (compact ? 32 : 40));
  return {
    left,
    right,
    top,
    bottom,
    width: right - left,
    height: bottom - top,
    centerX: (left + right) / 2,
    centerY: (top + bottom) / 2,
  };
}

function niceGridStep(value: number): number {
  if (!Number.isFinite(value) || value <= 0) return 100;
  const exponent = Math.floor(Math.log10(value));
  const fraction = value / 10 ** exponent;
  const niceFraction =
    fraction <= 1
      ? 1
      : fraction <= 2
        ? 2
        : fraction <= 2.5
          ? 2.5
          : fraction <= 5
            ? 5
            : 10;
  return niceFraction * 10 ** exponent;
}

function axisTicks(minimum: number, maximum: number, step: number): AxisTick[] {
  if (
    !Number.isFinite(minimum) ||
    !Number.isFinite(maximum) ||
    !Number.isFinite(step) ||
    step <= 0 ||
    maximum < minimum
  ) {
    return [];
  }
  const first = Math.ceil(minimum / step - 1e-9);
  const last = Math.floor(maximum / step + 1e-9);
  if (last - first > 300) return [];
  const result: AxisTick[] = [];
  for (let index = first; index <= last; index += 1) {
    const value = index * step;
    result.push({ value, screen: 0 });
  }
  return result;
}

function isMajorTick(value: number, majorStep: number): boolean {
  return Math.abs(value / majorStep - Math.round(value / majorStep)) < 1e-7;
}

function formatAxisValue(value: number): string {
  const rounded = Math.abs(value) < 1e-9 ? 0 : value;
  const absolute = Math.abs(rounded);
  if (absolute >= 10_000) {
    return `${Math.round(rounded / 1_000)}k`;
  }
  if (absolute >= 1_000) {
    const compact = rounded / 1_000;
    return `${Number.isInteger(compact) ? compact.toFixed(0) : compact.toFixed(1)}k`;
  }
  if (absolute >= 10) return rounded.toFixed(0);
  if (absolute === 0) return "0";
  return rounded.toFixed(1).replace(/\.0$/, "");
}

function buildCoordinateGrid(
  view: { x: number; y: number; scale: number },
  plot: PlotArea,
): CoordinateGrid {
  const targetSpacing = clamp(
    72 * Math.sqrt(0.65 / Math.max(0.12, view.scale)),
    44,
    128,
  );
  const majorStep = niceGridStep(targetSpacing / view.scale);
  const majorScreenSpacing = majorStep * view.scale;
  const showMinor = majorScreenSpacing >= 76;
  const minorStep = showMinor ? majorStep / 2 : majorStep;
  const worldLeft = (plot.left - view.x) / view.scale;
  const worldRight = (plot.right - view.x) / view.scale;
  const worldTop = (plot.top - view.y) / view.scale;
  const worldBottom = (plot.bottom - view.y) / view.scale;

  const xMajor = axisTicks(worldLeft, worldRight, majorStep).map((tick) => ({
    ...tick,
    screen: view.x + tick.value * view.scale,
  }));
  const yMajor = axisTicks(worldTop, worldBottom, majorStep).map((tick) => ({
    ...tick,
    screen: view.y + tick.value * view.scale,
  }));
  const xMinor = showMinor
    ? axisTicks(worldLeft, worldRight, minorStep)
        .filter((tick) => !isMajorTick(tick.value, majorStep))
        .map((tick) => ({
          ...tick,
          screen: view.x + tick.value * view.scale,
        }))
    : [];
  const yMinor = showMinor
    ? axisTicks(worldTop, worldBottom, minorStep)
        .filter((tick) => !isMajorTick(tick.value, majorStep))
        .map((tick) => ({
          ...tick,
          screen: view.y + tick.value * view.scale,
        }))
    : [];

  return { majorStep, xMajor, xMinor, yMajor, yMinor };
}

function truncateLabel(value: string, maxChars: number): string {
  const clean = value.trim();
  if (clean.length <= maxChars) return clean;
  return `${clean.slice(0, maxChars - 1).trimEnd()}…`;
}

function shortStatus(performance: GraphPerformance): string {
  if (performance === "ahead") return "Ahead";
  if (performance === "behind") return "Behind";
  if (performance === "in_line") return "In line";
  if (performance === "needs_review") return "Needs review";
  return "Not available";
}

function statusTextClass(performance: GraphPerformance): string {
  if (performance === "ahead") return "text-emerald-300";
  if (performance === "behind") return "text-rose-300";
  if (performance === "needs_review") return "text-amber-300";
  return "text-parchment-300";
}

function labelTierFor(scale: number, count: number): LabelTier {
  if (count > 120) {
    if (scale >= 1.5) return "full";
    if (scale >= 0.95) return "primary";
    return "focus";
  }
  if (count > 50) {
    if (scale >= 1.2) return "full";
    if (scale >= 0.78) return "primary";
    return "focus";
  }
  if (scale >= 1) return "full";
  if (scale >= 0.52) return "primary";
  return "focus";
}

function boundsForClusters(
  layout: GraphLayout,
  clusterIds: Set<string>,
): GraphBounds {
  const clusters = layout.clusters.filter((item) => clusterIds.has(item.id));
  if (clusters.length === 0) return layout.bounds;
  const padding = 38;
  const minX = Math.min(
    ...clusters.map((item) => item.x - item.separationRadius - padding),
  );
  const maxX = Math.max(
    ...clusters.map((item) => item.x + item.separationRadius + padding),
  );
  const minY = Math.min(
    ...clusters.map((item) => item.y - item.outerRadius - padding),
  );
  const maxY = Math.max(
    ...clusters.map(
      (item) => item.y + item.labelY + item.labelHeight + padding,
    ),
  );
  return {
    minX,
    maxX,
    minY,
    maxY,
    width: Math.max(1, maxX - minX),
    height: Math.max(1, maxY - minY),
    centerX: (minX + maxX) / 2,
    centerY: (minY + maxY) / 2,
  };
}

function reviewLabel(cluster: BenchmarkGraphCluster): string {
  if (cluster.stats.folio_count === 0) return "Awaiting folios";
  if (cluster.stats.average_difference !== null) {
    return `Avg diff ${formatPercent(cluster.stats.average_difference)}`;
  }
  if (cluster.review_state === "needs_mapping") return "Needs mapping";
  if (cluster.review_state === "needs_review") return "Needs review";
  if (cluster.review_state === "levels_missing") return "Levels missing";
  if (cluster.review_state === "no_comparison") return "No comparison";
  return "Comparison pending";
}

function reviewLabelColor(cluster: BenchmarkGraphCluster): string {
  if (cluster.stats.average_difference !== null) {
    if (cluster.stats.average_difference > 0) return "#236c4f";
    if (cluster.stats.average_difference < 0) return "#a8424e";
    return "#5f574e";
  }
  if (
    cluster.review_state === "needs_mapping" ||
    cluster.review_state === "needs_review" ||
    cluster.review_state === "levels_missing"
  ) {
    return "#93600f";
  }
  return "#6f675f";
}

function clusterSummaryParts(cluster: BenchmarkGraphCluster): Array<{
  text: string;
  color: string;
}> {
  const stats = cluster.stats;
  if (stats.folio_count === 0) {
    return [{ text: "No folios mapped", color: "#6f675f" }];
  }
  const parts: Array<{ text: string; color: string }> = [];
  if (stats.ahead > 0) {
    parts.push({ text: `${stats.ahead} ahead`, color: "#236c4f" });
  }
  if (stats.behind > 0) {
    parts.push({ text: `${stats.behind} behind`, color: "#a8424e" });
  }
  if (stats.in_line > 0) {
    parts.push({ text: `${stats.in_line} in line`, color: "#5f574e" });
  }
  if (stats.not_available > 0) {
    parts.push({
      text: `${stats.not_available} not available`,
      color: "#6f675f",
    });
  }
  if (stats.needs_review > 0) {
    parts.push({ text: `${stats.needs_review} review`, color: "#93600f" });
  }
  // Add cluster-level TRI return info
  if (stats.avg_holding_days !== undefined && stats.avg_holding_days !== null) {
    parts.push({
      text: `Avg hold: ${stats.avg_holding_days}d`,
      color: "#6f675f",
    });
  }
  if (stats.benchmark_tri_return !== undefined && stats.benchmark_tri_return !== null) {
    const diff = stats.benchmark_return_difference;
    const diffText = diff !== undefined && diff !== null
      ? (diff >= 0 ? `+${diff.toFixed(1)}%` : `${diff.toFixed(1)}%`)
      : "N/A";
    parts.push({
      text: `TRI: ${stats.benchmark_tri_return.toFixed(1)}% (${diffText})`,
      color: stats.benchmark_return_difference !== undefined && stats.benchmark_return_difference !== null && stats.benchmark_return_difference > 0
        ? "#236c4f"
        : stats.benchmark_return_difference !== undefined && stats.benchmark_return_difference !== null && stats.benchmark_return_difference < 0
          ? "#a8424e"
          : "#6f675f",
    });
  } else if (stats.benchmark_tri_return_note) {
    parts.push({
      text: `TRI: ${stats.benchmark_tri_return_note}`,
      color: "#a8424e",
    });
  }
  return parts.length
    ? parts
    : [{ text: "No comparison", color: "#6f675f" }];
}

function clusterSummaryText(cluster: BenchmarkGraphCluster): string {
  return clusterSummaryParts(cluster)
    .map((part) => part.text)
    .join(" · ");
}

function nameLabelWidth(
  cluster: BenchmarkGraphCluster,
  labelLines: string[],
): number {
  const summary = clusterSummaryText(cluster);
  const countText = `${cluster.stats.folio_count} folio${
    cluster.stats.folio_count === 1 ? "" : "s"
  }`;
  const longest = Math.max(
    ...labelLines.map((line) => line.length),
    summary.length * 0.82,
    countText.length * 0.9,
    18,
  );
  return Math.max(118, longest * 6.8 + 26);
}

function boxesOverlap(
  left: number,
  top: number,
  right: number,
  bottom: number,
  boxes: LabelBox[],
  padding = 3,
): boolean {
  return boxes.some(
    (box) =>
      left - padding < box.right &&
      right + padding > box.left &&
      top - padding < box.bottom &&
      bottom + padding > box.top,
  );
}

function TooltipRow({
  label,
  value,
  valueClass = "text-parchment-200",
}: {
  label: string;
  value: string;
  valueClass?: string;
}) {
  return (
    <div className="flex items-start justify-between gap-3">
      <span className="text-parchment-400">{label}</span>
      <span className={`text-right font-medium tabular-nums ${valueClass}`}>
        {value}
      </span>
    </div>
  );
}

function StatusPill({ performance }: { performance: GraphPerformance }) {
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full px-2 py-0.5 text-[10px] font-semibold ring-1 ring-inset ${STATUS_PILL[performance]}`}
    >
      {shortStatus(performance)}
    </span>
  );
}

function FolioTooltipContent({ folio }: { folio: BenchmarkGraphFolio }) {
  const benchmarkLabel =
    folio.benchmark_return_type === "xirr"
      ? "Benchmark XIRR"
      : folio.benchmark_return_type === "absolute"
        ? "Benchmark return"
        : "Benchmark return / XIRR";
  const differenceClass =
    folio.benchmark_difference === null
      ? "text-parchment-400"
      : folio.benchmark_difference > 0
        ? "text-emerald-300"
        : folio.benchmark_difference < 0
          ? "text-rose-300"
          : "text-parchment-300";

  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-[13px] font-semibold text-parchment-50">
            {folio.client_name}
          </p>
          <p className="mt-0.5 font-mono text-[10px] text-copper-300">
            {folio.folio_number}
          </p>
        </div>
        <StatusPill performance={folio.performance} />
      </div>
      <p className="mt-2 text-[11px] font-medium leading-4 text-parchment-200">
        {folio.scheme_name}
      </p>
      <p className="mt-1 text-[10px] text-parchment-400">
        vs <span className="text-parchment-300">{folio.benchmark_name}</span>
      </p>

      <div className="mt-2.5 space-y-1 border-t border-warm-100/15 pt-2.5 text-[10.5px]">
        <TooltipRow
          label="Current value"
          value={folio.aum === null ? "Not available" : formatCurrency(folio.aum)}
          valueClass={folio.aum === null ? "text-parchment-400" : "text-parchment-100"}
        />
        <TooltipRow
          label="Absolute return"
          value={formatPercent(folio.absolute_return)}
        />
        <TooltipRow label="XIRR" value={formatPercent(folio.xirr)} />
        <TooltipRow
          label={benchmarkLabel}
          value={formatPercent(folio.benchmark_return)}
        />
        <TooltipRow
          label="Difference"
          value={formatPercent(folio.benchmark_difference)}
          valueClass={differenceClass}
        />
        <div className="flex items-center justify-between gap-3 pt-0.5">
          <span className="text-parchment-400">Status</span>
          <span className={`font-semibold ${statusTextClass(folio.performance)}`}>
            {performanceLabel(folio.performance)}
          </span>
        </div>
      </div>

      {folio.benchmark_difference === null &&
        folio.benchmark_comparison_note && (
          <p className="mt-2 line-clamp-2 border-t border-warm-100/15 pt-2 text-[10px] leading-4 text-parchment-400">
            {folio.benchmark_comparison_note}
          </p>
        )}
      {(folio.benchmark_missing_date_count ?? 0) > 0 ? (
        <p className="mt-1 text-[10px] font-medium leading-4 text-amber-300">
          {folio.benchmark_missing_date_count?.toLocaleString("en-IN")} local
          benchmark date(s) missing. Select the folio for details.
        </p>
      ) : null}
    </div>
  );
}

function ClusterTooltipContent({ cluster }: { cluster: BenchmarkGraphCluster }) {
  const stats = cluster.stats;
  return (
    <div>
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-[13px] font-semibold leading-5 text-parchment-50">
            {cluster.name}
          </p>
          <p className="mt-0.5 text-[10px] text-parchment-400">
            {stats.folio_count} folio{stats.folio_count === 1 ? "" : "s"}
          </p>
        </div>
        <span className="inline-flex shrink-0 items-center rounded-full bg-copper-400/10 px-2 py-0.5 text-[10px] font-semibold text-copper-300 ring-1 ring-inset ring-copper-400/25">
          Benchmark
        </span>
      </div>

      <div className="mt-2.5 grid grid-cols-2 gap-x-4 gap-y-1.5 border-t border-warm-100/15 pt-2.5 text-[10.5px]">
        <TooltipRow
          label="Ahead"
          value={String(stats.ahead)}
          valueClass="text-emerald-300"
        />
        <TooltipRow
          label="Behind"
          value={String(stats.behind)}
          valueClass="text-rose-300"
        />
        <TooltipRow
          label="Not available"
          value={String(stats.not_available)}
          valueClass="text-parchment-300"
        />
        <TooltipRow
          label="Needs review"
          value={String(stats.needs_review)}
          valueClass="text-amber-300"
        />
      </div>

      <div className="mt-2.5 border-t border-warm-100/15 pt-2.5">
        <p className="text-[10px] uppercase tracking-[0.12em] text-parchment-500">
          Average folio performance
        </p>
        <p
          className={`mt-0.5 text-lg font-semibold tabular-nums ${
            stats.average_difference === null
              ? "text-parchment-300"
              : stats.average_difference > 0
                ? "text-emerald-300"
                : stats.average_difference < 0
                  ? "text-rose-300"
                  : "text-parchment-200"
          }`}
        >
          {formatPercent(stats.average_difference)}
        </p>
        <p className="mt-0.5 text-[10px] text-parchment-400">
          Across {stats.available} comparable folio
          {stats.available === 1 ? "" : "s"} · positive means ahead
        </p>
      </div>
    </div>
  );
}

const BenchmarkGraph = forwardRef<BenchmarkGraphHandle, Props>(
  function BenchmarkGraph(
    {
      layout,
      clusters,
      visibleClusterIds,
      visibleFolioIds,
      matchedClusterIds,
      matchedFolioIds,
      matchCount,
      searchActive,
      filterKey,
      searchKey,
      selectedClusterId,
      selectedFolioId,
      onSelectCluster,
      onSelectFolio,
      onClearSelection,
      fullscreen = false,
      onToggleFullscreen,
    },
    ref,
  ) {
    const containerRef = useRef<HTMLDivElement | null>(null);
    const [size, setSize] = useState({ width: 0, height: 0 });
    const [view, setView] = useState({ x: 0, y: 0, scale: 1 });
    const viewRef = useRef(view);
    const plot = useMemo(
      () => plotAreaFor(size.width, size.height),
      [size.height, size.width],
    );
    const grid = useMemo(() => buildCoordinateGrid(view, plot), [plot, view]);
    const [panning, setPanning] = useState(false);
    const [hovered, setHovered] = useState<HoverState | null>(null);
    const animationRef = useRef<number | null>(null);
    const panRef = useRef<{
      pointerId: number;
      startX: number;
      startY: number;
      originX: number;
      originY: number;
      scale: number;
    } | null>(null);
    const draggedRef = useRef(false);
    const fittedKeyRef = useRef("");

    const clusterById = useMemo(
      () => new Map(clusters.map((cluster) => [cluster.id, cluster])),
      [clusters],
    );
    const folioById = useMemo(() => {
      const result = new Map<string, BenchmarkGraphFolio>();
      for (const cluster of clusters) {
        for (const folio of cluster.folios) result.set(folio.id, folio);
      }
      return result;
    }, [clusters]);
    const layoutClusterById = useMemo(
      () => new Map(layout.clusters.map((cluster) => [cluster.id, cluster])),
      [layout.clusters],
    );
    const layoutFolioById = useMemo(
      () => new Map(layout.folios.map((folio) => [folio.id, folio])),
      [layout.folios],
    );

    const visibleClusters = useMemo(
      () =>
        layout.clusters.filter((cluster) =>
          visibleClusterIds.has(cluster.id),
        ),
      [layout.clusters, visibleClusterIds],
    );
    const visibleFolios = useMemo(
      () =>
        layout.folios.filter(
          (folio) =>
            visibleFolioIds.has(folio.id) &&
            visibleClusterIds.has(folio.clusterId),
        ),
      [layout.folios, visibleClusterIds, visibleFolioIds],
    );
    const foliosByCluster = useMemo(() => {
      const result = new Map<string, PositionedFolio[]>();
      for (const folio of visibleFolios) {
        const list = result.get(folio.clusterId) ?? [];
        list.push(folio);
        result.set(folio.clusterId, list);
      }
      return result;
    }, [visibleFolios]);

    useEffect(() => {
      viewRef.current = view;
    }, [view]);

    useEffect(() => {
      return () => {
        if (animationRef.current !== null) {
          cancelAnimationFrame(animationRef.current);
        }
      };
    }, []);

    const stopAnimation = useCallback(() => {
      if (animationRef.current !== null) {
        cancelAnimationFrame(animationRef.current);
        animationRef.current = null;
      }
    }, []);

    const animateView = useCallback(
      (target: { x: number; y: number; scale: number }, duration = 240) => {
        stopAnimation();
        if (size.width <= 0 || size.height <= 0) return;
        const from = viewRef.current;
        if (
          document.visibilityState !== "visible" ||
          (Math.abs(from.x - target.x) < 0.5 &&
            Math.abs(from.y - target.y) < 0.5 &&
            Math.abs(from.scale - target.scale) < 0.002)
        ) {
          setView(target);
          viewRef.current = target;
          return;
        }
        const started = performance.now();
        const step = (now: number) => {
          const progress = Math.min(1, (now - started) / duration);
          const eased = 1 - Math.pow(1 - progress, 3);
          const next = {
            x: from.x + (target.x - from.x) * eased,
            y: from.y + (target.y - from.y) * eased,
            scale: from.scale + (target.scale - from.scale) * eased,
          };
          setView(next);
          viewRef.current = next;
          if (progress < 1) {
            animationRef.current = requestAnimationFrame(step);
          } else {
            animationRef.current = null;
          }
        };
        animationRef.current = requestAnimationFrame(step);
      },
      [size.height, size.width, stopAnimation],
    );

    const fitBounds = useCallback(
      (bounds: GraphBounds, maxScale = 1.2) => {
        if (size.width <= 0 || size.height <= 0) return;
        const padding = 22;
        const scale = clamp(
          Math.min(
            Math.max(1, plot.width - padding * 2) / bounds.width,
            Math.max(1, plot.height - padding * 2) / bounds.height,
          ),
          0.1,
          maxScale,
        );
        animateView({
          x: plot.centerX - bounds.centerX * scale,
          y: plot.centerY - bounds.centerY * scale,
          scale,
        });
      },
      [animateView, plot, size.height, size.width],
    );

    const fitAll = useCallback(() => {
      fitBounds(boundsForClusters(layout, visibleClusterIds), 1.2);
    }, [fitBounds, layout, visibleClusterIds]);

    const focusCluster = useCallback(
      (clusterId: string) => {
        fitBounds(boundsForClusters(layout, new Set([clusterId])), 1.45);
      },
      [fitBounds, layout],
    );

    const focusMatches = useCallback(() => {
      const points: Array<{ x: number; y: number; radius: number }> = [];
      for (const cluster of layout.clusters) {
        if (matchedClusterIds.has(cluster.id)) {
          points.push({
            x: cluster.x,
            y: cluster.y,
            radius: cluster.clusterRadius,
          });
        }
      }
      for (const folio of layout.folios) {
        if (matchedFolioIds.has(folio.id)) {
          points.push({
            x: folio.x,
            y: folio.y,
            radius: layout.folioRadius + 12,
          });
        }
      }
      if (points.length === 0) {
        fitAll();
        return;
      }
      const padding = 36;
      const minX = Math.min(...points.map((item) => item.x - item.radius - padding));
      const maxX = Math.max(...points.map((item) => item.x + item.radius + padding));
      const minY = Math.min(...points.map((item) => item.y - item.radius - padding));
      const maxY = Math.max(...points.map((item) => item.y + item.radius + padding));
      fitBounds(
        {
          minX,
          maxX,
          minY,
          maxY,
          width: Math.max(1, maxX - minX),
          height: Math.max(1, maxY - minY),
          centerX: (minX + maxX) / 2,
          centerY: (minY + maxY) / 2,
        },
        1.4,
      );
    }, [
      fitAll,
      fitBounds,
      layout.clusters,
      layout.folioRadius,
      layout.folios,
      matchedClusterIds,
      matchedFolioIds,
    ]);

    const zoomBy = useCallback(
      (factor: number) => {
        if (size.width <= 0 || size.height <= 0) return;
        const current = viewRef.current;
        const nextScale = clamp(current.scale * factor, 0.12, 4);
        if (nextScale === current.scale) return;
        const centerX = plot.centerX;
        const centerY = plot.centerY;
        const graphX = (centerX - current.x) / current.scale;
        const graphY = (centerY - current.y) / current.scale;
        animateView(
          {
            x: centerX - graphX * nextScale,
            y: centerY - graphY * nextScale,
            scale: nextScale,
          },
          170,
        );
      },
      [animateView, plot, size.height, size.width],
    );

    useImperativeHandle(
      ref,
      () => ({
        resetView: () => {
          onClearSelection();
          fitAll();
        },
        fitToScreen: fitAll,
        focusCluster,
        focusMatches,
        zoomIn: () => zoomBy(1.32),
        zoomOut: () => zoomBy(1 / 1.32),
      }),
      [fitAll, focusCluster, focusMatches, onClearSelection, zoomBy],
    );

    useEffect(() => {
      const element = containerRef.current;
      if (!element) return;

      function measure() {
        const rect = element!.getBoundingClientRect();
        setSize({
          width: Math.max(1, rect.width),
          height: Math.max(1, rect.height),
        });
      }

      const observer = new ResizeObserver(measure);
      observer.observe(element);
      // ResizeObserver can miss the first layout when a tab starts hidden or
      // when the graph mounts in a background tab. Measure once explicitly and
      // again when the document becomes visible or the window is resized.
      measure();
      const frame = requestAnimationFrame(measure);
      window.addEventListener("resize", measure);
      document.addEventListener("visibilitychange", measure);
      return () => {
        cancelAnimationFrame(frame);
        window.removeEventListener("resize", measure);
        document.removeEventListener("visibilitychange", measure);
        observer.disconnect();
      };
    }, []);

    useEffect(() => {
      const element = containerRef.current;
      if (!element) return;
      const target = element;
      function handleWheel(event: WheelEvent) {
        event.preventDefault();
        stopAnimation();
        const rect = target.getBoundingClientRect();
        const pointerX = event.clientX - rect.left;
        const pointerY = event.clientY - rect.top;
        setView((current) => {
          const factor = Math.exp(-event.deltaY * 0.0015);
          const nextScale = clamp(current.scale * factor, 0.12, 4);
          if (nextScale === current.scale) return current;
          const graphX = (pointerX - current.x) / current.scale;
          const graphY = (pointerY - current.y) / current.scale;
          return {
            x: pointerX - graphX * nextScale,
            y: pointerY - graphY * nextScale,
            scale: nextScale,
          };
        });
      }
      target.addEventListener("wheel", handleWheel, { passive: false });
      return () => target.removeEventListener("wheel", handleWheel);
    }, [stopAnimation]);

    useEffect(() => {
      if (size.width <= 0 || size.height <= 0) return;
      const key = `${Math.round(size.width)}x${Math.round(size.height)}|${filterKey}|${searchKey}`;
      if (fittedKeyRef.current === key) return;
      fittedKeyRef.current = key;
      if (
        searchActive &&
        (matchedClusterIds.size > 0 || matchedFolioIds.size > 0)
      ) {
        focusMatches();
      } else {
        fitAll();
      }
    }, [
      filterKey,
      fitAll,
      focusMatches,
      matchedClusterIds,
      matchedFolioIds,
      searchActive,
      searchKey,
      size.height,
      size.width,
    ]);

    const labelTier = labelTierFor(view.scale, visibleFolios.length);

    const folioLabels = useMemo(() => {
      const occupied: LabelBox[] = [];
      for (const cluster of visibleClusters) {
        occupied.push({
          left: cluster.x - cluster.nucleusRadius - 4,
          top: cluster.y - cluster.nucleusRadius - 4,
          right: cluster.x + cluster.nucleusRadius + 4,
          bottom: cluster.y + cluster.nucleusRadius + 4,
        });
        const width = nameLabelWidth(
          clusterById.get(cluster.id)!,
          cluster.labelLines,
        );
        occupied.push({
          left: cluster.x - width / 2,
          top: cluster.y + cluster.labelY,
          right: cluster.x + width / 2,
          bottom: cluster.y + cluster.labelY + cluster.labelHeight,
        });
      }
      for (const folio of visibleFolios) {
        occupied.push({
          left: folio.x - layout.folioRadius - 2,
          top: folio.y - layout.folioRadius - 2,
          right: folio.x + layout.folioRadius + 2,
          bottom: folio.y + layout.folioRadius + 2,
        });
      }

      const priority = (folio: PositionedFolio): number => {
        if (selectedFolioId === folio.id) return 0;
        if (hovered?.kind === "folio" && hovered.id === folio.id) return 1;
        if (matchedFolioIds.has(folio.id)) return 2;
        return 3;
      };
      const ordered = [...visibleFolios].sort(
        (left, right) => priority(left) - priority(right),
      );
      const labels: RenderFolioLabel[] = [];

      for (const folio of ordered) {
        const data = folioById.get(folio.id);
        const cluster = layoutClusterById.get(folio.clusterId);
        const clusterData = clusterById.get(folio.clusterId);
        if (!data || !cluster || !clusterData) continue;
        const focused =
          selectedFolioId === folio.id ||
          (hovered?.kind === "folio" && hovered.id === folio.id) ||
          matchedFolioIds.has(folio.id);
        if (labelTier === "focus" && !focused) continue;

        const showSecondary =
          labelTier === "full" || (labelTier === "focus" && focused);
        const primaryMax = showSecondary ? 28 : 21;
        const primary = truncateLabel(data.client_name, primaryMax);
        const secondary = showSecondary
          ? truncateLabel(data.scheme_name, 30)
          : null;
        const anchor: "start" | "end" =
          folio.x >= cluster.x ? "start" : "end";
        const gap = layout.folioRadius + 8;
        const primaryWidth = Math.max(primary.length * 6.7, 30);
        const fullWidth = Math.max(
          primaryWidth,
          (secondary?.length ?? 0) * 5.6,
        );

        function candidatePositions(
          isSecondary: boolean,
        ): Array<{
          anchor: "start" | "end" | "middle";
          x: number;
          centerY: number;
        }> {
          const labelGap = layout.folioRadius + 8;
          const verticalOffset = isSecondary ? 12 : 6;
          return [
            {
              anchor,
              x: anchor === "start" ? folio.x + gap : folio.x - gap,
              centerY: folio.y,
            },
            {
              anchor: anchor === "start" ? "end" : "start",
              x: anchor === "start" ? folio.x - gap : folio.x + gap,
              centerY: folio.y,
            },
            {
              anchor: "middle" as const,
              x: folio.x,
              centerY: folio.y + labelGap + verticalOffset,
            },
            {
              anchor: "middle" as const,
              x: folio.x,
              centerY: folio.y - labelGap - verticalOffset,
            },
          ];
        }

        function attemptPlacement(
          secondaryText: string | null,
          labelWidth: number,
          labelHeight: number,
        ): RenderFolioLabel | null {
          for (const candidate of candidatePositions(secondaryText !== null)) {
            const boxWidth = labelWidth + 4;
            const boxTop = candidate.centerY - (secondaryText ? 12 : 8);
            const boxLeft =
              candidate.anchor === "middle"
                ? candidate.x - boxWidth / 2
                : candidate.anchor === "start"
                  ? candidate.x - 2
                  : candidate.x - labelWidth - 2;
            if (
              boxesOverlap(
                boxLeft,
                boxTop,
                boxLeft + boxWidth,
                boxTop + labelHeight,
                occupied,
              )
            ) {
              continue;
            }
            const result: RenderFolioLabel = {
              id: folio.id,
              anchor: candidate.anchor,
              x: candidate.x,
              primary,
              secondary: secondaryText,
              primaryY: secondaryText
                ? candidate.centerY - 1
                : candidate.centerY + 3,
              secondaryY: secondaryText ? candidate.centerY + 10 : null,
              width: labelWidth,
              height: labelHeight,
              boxLeft,
              boxTop,
              emphasis: focused,
            };
            occupied.push({
              left: boxLeft,
              top: boxTop,
              right: boxLeft + boxWidth,
              bottom: boxTop + labelHeight,
            });
            return result;
          }
          return null;
        }

        let placed = attemptPlacement(
          secondary,
          fullWidth,
          secondary ? 24 : 16,
        );
        if (!placed && secondary) {
          placed = attemptPlacement(null, primaryWidth, 16);
        }
        if (!placed) continue;
        labels.push(placed);
      }
      return labels;
    }, [
      clusterById,
      hovered,
      labelTier,
      layout.folioRadius,
      layoutClusterById,
      matchedFolioIds,
      selectedFolioId,
      folioById,
      visibleClusters,
      visibleFolios,
    ]);

    function handlePointerDown(event: ReactPointerEvent<SVGSVGElement>) {
      if (event.button !== 0) return;
      stopAnimation();
      panRef.current = {
        pointerId: event.pointerId,
        startX: event.clientX,
        startY: event.clientY,
        originX: view.x,
        originY: view.y,
        scale: view.scale,
      };
      draggedRef.current = false;
      setPanning(true);
      event.currentTarget.setPointerCapture(event.pointerId);
    }

    function handlePointerMove(event: ReactPointerEvent<SVGSVGElement>) {
      const pan = panRef.current;
      if (!pan || pan.pointerId !== event.pointerId) return;
      const dx = event.clientX - pan.startX;
      const dy = event.clientY - pan.startY;
      if (Math.hypot(dx, dy) > 3) draggedRef.current = true;
      setView({
        x: pan.originX + dx,
        y: pan.originY + dy,
        scale: pan.scale,
      });
    }

    function endPan(event: ReactPointerEvent<SVGSVGElement>) {
      const pan = panRef.current;
      if (pan && event.currentTarget.hasPointerCapture(pan.pointerId)) {
        event.currentTarget.releasePointerCapture(pan.pointerId);
      }
      panRef.current = null;
      setPanning(false);
    }

    function handleBackgroundClick() {
      if (draggedRef.current) {
        draggedRef.current = false;
        return;
      }
      onClearSelection();
    }

    function nodeEnter(
      event: ReactMouseEvent,
      kind: HoverState["kind"],
      id: string,
    ) {
      const rect = containerRef.current?.getBoundingClientRect();
      if (!rect) return;
      setHovered({
        kind,
        id,
        x: event.clientX - rect.left,
        y: event.clientY - rect.top,
      });
    }

    const hoveredFolio =
      hovered?.kind === "folio" ? folioById.get(hovered.id) : null;
    const hoveredCluster =
      hovered?.kind === "cluster" ? clusterById.get(hovered.id) : null;

    const tooltipWidth = Math.min(340, Math.max(250, size.width - 24));
    const tooltipHeight = hoveredFolio ? 340 : 220;
    const preferredTooltipLeft = hovered
      ? hovered.x + 18 + tooltipWidth > size.width - 12
        ? hovered.x - tooltipWidth - 18
        : hovered.x + 18
      : 0;
    const tooltipLeft = hovered
      ? Math.max(
          12,
          Math.min(preferredTooltipLeft, size.width - tooltipWidth - 12),
        )
      : 0;
    const tooltipTop = hovered
      ? Math.max(12, Math.min(hovered.y + 14, size.height - tooltipHeight))
      : 0;
    const canZoomIn = view.scale < 3.999;
    const canZoomOut = view.scale > 0.1201;

    function renderClusterLabel(cluster: PositionedCluster) {
      const data = clusterById.get(cluster.id);
      if (!data) return null;
      const width = nameLabelWidth(data, cluster.labelLines);
      const summary = clusterSummaryParts(data);
      const countText = `${data.stats.folio_count} folio${
        data.stats.folio_count === 1 ? "" : "s"
      }`;
      const matched = matchedClusterIds.has(cluster.id);
      const dimmed = searchActive && !matched;
      const top = cluster.y + cluster.labelY;
      return (
        <g
          key={`label-${cluster.id}`}
          opacity={dimmed ? 0.3 : 1}
          pointerEvents="none"
        >
          <rect
            fill="#fff8f0"
            fillOpacity={0.94}
            height={cluster.labelHeight}
            rx={9}
            stroke={matched ? "#9a542c" : "#b9a18b"}
            strokeOpacity={matched ? 0.95 : 0.7}
            strokeWidth={matched ? 1.4 : 0.8}
            width={width}
            x={cluster.x - width / 2}
            y={top}
          />
          {cluster.labelLines.map((line, index) => (
            <text
              fill="#2a211b"
              fontSize={12.5}
              fontWeight={700}
              key={line + index}
              textAnchor="middle"
              x={cluster.x}
              y={top + 15 + index * 13}
            >
              {line}
            </text>
          ))}
          <text
            fill="#8a5a39"
            fontSize={10}
            fontWeight={700}
            textAnchor="middle"
            x={cluster.x}
            y={top + cluster.labelLines.length * 13 + 14}
          >
            {countText}
          </text>
          <text
            fontSize={9.5}
            fontWeight={600}
            textAnchor="middle"
            x={cluster.x}
            y={top + cluster.labelLines.length * 13 + 27}
          >
            {summary.map((part, index) => (
              <tspan fill={part.color} key={part.text}>
                {index > 0 ? " · " : ""}
                {part.text}
              </tspan>
            ))}
          </text>
          <text
            fill={reviewLabelColor(data)}
            fontSize={9}
            fontWeight={500}
            textAnchor="middle"
            x={cluster.x}
            y={top + cluster.labelLines.length * 13 + 39}
          >
            {reviewLabel(data)}
          </text>
        </g>
      );
    }

    return (
      <div
        className={graphCanvasClass(fullscreen)}
        ref={containerRef}
      >
        <svg
          aria-label="Benchmark cluster graph. Drag to pan, scroll to zoom, and click a node for details."
          className="h-full w-full touch-none select-none"
          onPointerDown={handlePointerDown}
          onPointerLeave={endPan}
          onPointerMove={handlePointerMove}
          onPointerUp={endPan}
          role="img"
          style={{ cursor: panning ? "grabbing" : "grab" }}
        >
          <defs>
            <clipPath id="graph-plot-clip">
              <rect
                height={plot.height}
                width={plot.width}
                x={plot.left}
                y={plot.top}
              />
            </clipPath>
            <radialGradient id="graph-halo" cx="50%" cy="45%" r="60%">
              <stop offset="0%" stopColor="#9a542c" stopOpacity="0.12" />
              <stop offset="100%" stopColor="#9a542c" stopOpacity="0" />
            </radialGradient>
            <radialGradient id="nucleus-fill" cx="38%" cy="32%" r="72%">
              <stop offset="0%" stopColor="#7a5a43" />
              <stop offset="55%" stopColor="#433229" />
              <stop offset="100%" stopColor="#231c17" />
            </radialGradient>
          </defs>
          <rect fill="#f4e8dc" height="100%" width="100%" />
          <g
            aria-hidden="true"
            data-grid-major-step={grid.majorStep}
            pointerEvents="none"
            shapeRendering="crispEdges"
          >
            {grid.xMinor.map((tick) => (
              <line
                data-grid-line="minor-x"
                data-grid-value={tick.value}
                key={`grid-minor-x-${tick.value}`}
                stroke="#8a6f5b"
                strokeOpacity="0.05"
                strokeWidth="1"
                x1={tick.screen}
                x2={tick.screen}
                y1={plot.top}
                y2={plot.bottom}
              />
            ))}
            {grid.yMinor.map((tick) => (
              <line
                data-grid-line="minor-y"
                data-grid-value={tick.value}
                key={`grid-minor-y-${tick.value}`}
                stroke="#8a6f5b"
                strokeOpacity="0.05"
                strokeWidth="1"
                x1={plot.left}
                x2={plot.right}
                y1={tick.screen}
                y2={tick.screen}
              />
            ))}
            {grid.xMajor.map((tick) => (
              <line
                data-grid-line="major-x"
                data-grid-value={tick.value}
                key={`grid-major-x-${tick.value}`}
                stroke="#7a5c47"
                strokeOpacity="0.11"
                strokeWidth="1"
                x1={tick.screen}
                x2={tick.screen}
                y1={plot.top}
                y2={plot.bottom}
              />
            ))}
            {grid.yMajor.map((tick) => (
              <line
                data-grid-line="major-y"
                data-grid-value={tick.value}
                key={`grid-major-y-${tick.value}`}
                stroke="#7a5c47"
                strokeOpacity="0.11"
                strokeWidth="1"
                x1={plot.left}
                x2={plot.right}
                y1={tick.screen}
                y2={tick.screen}
              />
            ))}
          </g>
          <rect
            fill="transparent"
            height="100%"
            onClick={handleBackgroundClick}
            width="100%"
          />
          <g clipPath="url(#graph-plot-clip)">
            <g transform={`translate(${view.x} ${view.y}) scale(${view.scale})`}>
            {visibleClusters.map((cluster) => (
              <circle
                cx={cluster.x}
                cy={cluster.y}
                fill="url(#graph-halo)"
                key={`halo-${cluster.id}`}
                opacity={
                  searchActive && !matchedClusterIds.has(cluster.id) ? 0.12 : 0.62
                }
                r={cluster.clusterRadius}
                stroke="#7e6a58"
                strokeDasharray="3 10"
                strokeOpacity={0.16}
              />
            ))}

            {visibleClusters.flatMap((cluster) => {
              const folios = foliosByCluster.get(cluster.id) ?? [];
              return folios.map((folio) => {
                const matched = matchedFolioIds.has(folio.id);
                const dimmed = searchActive && !matched;
                return (
                  <line
                    key={`link-${cluster.id}-${folio.id}`}
                    opacity={dimmed ? 0.05 : 0.26}
                    stroke={GRAPH_LINK_COLOR}
                    strokeWidth={0.9}
                    x1={cluster.x}
                    x2={folio.x}
                    y1={cluster.y}
                    y2={folio.y}
                  />
                );
              });
            })}

            {visibleClusters.map((cluster) => {
              const data = clusterById.get(cluster.id);
              if (!data) return null;
              const matched = matchedClusterIds.has(cluster.id);
              const dimmed = searchActive && !matched;
              const selected = selectedClusterId === cluster.id;
              return (
                <g
                  aria-label={`${cluster.name}, ${data.stats.folio_count} folio${
                    data.stats.folio_count === 1 ? "" : "s"
                  }, ${data.stats.ahead} ahead, ${data.stats.behind} behind, ${
                    data.stats.not_available
                  } not available`}
                  key={cluster.id}
                  onClick={(event) => {
                    event.stopPropagation();
                    onSelectCluster(cluster.id);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectCluster(cluster.id);
                    }
                  }}
                  onMouseEnter={(event) =>
                    nodeEnter(event, "cluster", cluster.id)
                  }
                  onMouseLeave={() => setHovered(null)}
                  onPointerDown={(event) => event.stopPropagation()}
                  opacity={dimmed ? 0.4 : 1}
                  role="button"
                  style={{ cursor: "pointer" }}
                  tabIndex={0}
                >
                  {selected && (
                    <circle
                      cx={cluster.x}
                      cy={cluster.y}
                      fill="none"
                      r={cluster.nucleusRadius + 8}
                      stroke="#7a4022"
                      strokeOpacity={0.95}
                      strokeWidth={2}
                    />
                  )}
                  {matched && (
                    <circle
                      cx={cluster.x}
                      cy={cluster.y}
                      fill="none"
                      r={cluster.nucleusRadius + 6}
                      stroke="#2a211b"
                      strokeDasharray="3 4"
                      strokeOpacity={0.9}
                      strokeWidth={1.6}
                    />
                  )}
                  <circle
                    cx={cluster.x}
                    cy={cluster.y}
                    fill="url(#nucleus-fill)"
                    r={cluster.nucleusRadius}
                    stroke="#2f241d"
                    strokeOpacity={0.95}
                    strokeWidth={1.6}
                  />
                  <text
                    fill="#fbf3e8"
                    fontSize={Math.round(cluster.nucleusRadius * 0.64)}
                    fontWeight={700}
                    textAnchor="middle"
                    x={cluster.x}
                    y={cluster.y + 1}
                  >
                    {data.stats.folio_count}
                  </text>
                  <text
                    fill="#d8b798"
                    fontSize={Math.max(6.5, cluster.nucleusRadius * 0.21)}
                    fontWeight={700}
                    letterSpacing="0.1em"
                    textAnchor="middle"
                    x={cluster.x}
                    y={cluster.y + cluster.nucleusRadius * 0.48}
                  >
                    FOLIOS
                  </text>
                </g>
              );
            })}

            {visibleClusters.map((cluster) => renderClusterLabel(cluster))}

            {visibleFolios.map((folio) => {
              const data = folioById.get(folio.id);
              if (!data) return null;
              const color = COLORS[folio.performance];
              const matched = matchedFolioIds.has(folio.id);
              const dimmed = searchActive && !matched;
              const selected = selectedFolioId === folio.id;
              const hoveredNode =
                hovered?.kind === "folio" && hovered.id === folio.id;
              return (
                <g
                  aria-label={`${data.client_name}, ${data.scheme_name}, ${data.folio_number}, vs ${data.benchmark_name}, ${performanceLabel(
                    data.performance,
                  )}`}
                  key={folio.id}
                  onClick={(event) => {
                    event.stopPropagation();
                    onSelectFolio(folio.id);
                  }}
                  onKeyDown={(event) => {
                    if (event.key === "Enter" || event.key === " ") {
                      event.preventDefault();
                      onSelectFolio(folio.id);
                    }
                  }}
                  onMouseEnter={(event) => nodeEnter(event, "folio", folio.id)}
                  onMouseLeave={() => setHovered(null)}
                  onPointerDown={(event) => event.stopPropagation()}
                  opacity={dimmed ? 0.22 : 1}
                  role="button"
                  style={{ cursor: "pointer" }}
                  tabIndex={0}
                >
                  {selected && (
                    <circle
                      cx={folio.x}
                      cy={folio.y}
                      fill="none"
                      r={layout.folioRadius + 6}
                      stroke="#2a211b"
                      strokeWidth={1.8}
                    />
                  )}
                  {matched && (
                    <circle
                      cx={folio.x}
                      cy={folio.y}
                      fill="none"
                      r={layout.folioRadius + 5}
                      stroke="#2a211b"
                      strokeDasharray="2 3"
                      strokeWidth={1.3}
                    />
                  )}
                  <circle
                    cx={folio.x}
                    cy={folio.y}
                    fill={color.fill}
                    r={layout.folioRadius + (hoveredNode ? 2.4 : 0)}
                    stroke={color.stroke}
                    strokeOpacity={0.95}
                    strokeWidth={1.1}
                  />
                </g>
              );
            })}

            {folioLabels.map((label) => (
              <g
                key={`folio-label-${label.id}`}
                opacity={searchActive && !matchedFolioIds.has(label.id) ? 0.4 : 1}
                pointerEvents="none"
              >
                {label.emphasis && (
                  <rect
                    fill="#fff8f0"
                    fillOpacity={0.95}
                    height={label.height}
                    rx={4}
                    stroke="#9a542c"
                    strokeOpacity={0.55}
                    width={label.width + 4}
                    x={label.boxLeft}
                    y={label.boxTop}
                  />
                )}
                <text
                  fill="#2a211b"
                  fontSize={10.5}
                  fontWeight={700}
                  paintOrder="stroke"
                  stroke="#f4e8dc"
                  strokeWidth={label.emphasis ? 0 : 3}
                  textAnchor={label.anchor}
                  x={label.x}
                  y={label.primaryY}
                >
                  {label.primary}
                </text>
                {label.secondary && label.secondaryY !== null && (
                  <text
                    fill="#6f5a49"
                    fontSize={8.6}
                    fontWeight={600}
                    paintOrder="stroke"
                    stroke="#f4e8dc"
                    strokeWidth={label.emphasis ? 0 : 2.6}
                    textAnchor={label.anchor}
                    x={label.x}
                    y={label.secondaryY}
                  >
                    {label.secondary}
                  </text>
                )}
              </g>
            ))}
            </g>
          </g>
          <g aria-hidden="true" pointerEvents="none" shapeRendering="crispEdges">
            <line
              data-axis="y"
              stroke="#6f5543"
              strokeOpacity="0.3"
              strokeWidth="1.2"
              x1={plot.left}
              x2={plot.left}
              y1={plot.top}
              y2={plot.bottom}
            />
            <line
              data-axis="x"
              stroke="#6f5543"
              strokeOpacity="0.3"
              strokeWidth="1.2"
              x1={plot.left}
              x2={plot.right}
              y1={plot.bottom}
              y2={plot.bottom}
            />
            {grid.xMajor.map((tick) => (
              <g data-axis-value={tick.value} key={`axis-x-${tick.value}`}>
                <line
                  data-axis-tick="x"
                  stroke="#6f5543"
                  strokeOpacity="0.36"
                  strokeWidth="1"
                  x1={tick.screen}
                  x2={tick.screen}
                  y1={plot.bottom}
                  y2={plot.bottom + 4}
                />
                <text
                  data-axis-label="x"
                  fill="#6f5a49"
                  fillOpacity="0.88"
                  fontFamily="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
                  fontSize="9.5"
                  fontWeight="600"
                  textAnchor="middle"
                  x={tick.screen}
                  y={plot.bottom + 16}
                >
                  {formatAxisValue(tick.value)}
                </text>
              </g>
            ))}
            {grid.yMajor.map((tick) => (
              <g data-axis-value={tick.value} key={`axis-y-${tick.value}`}>
                <line
                  data-axis-tick="y"
                  stroke="#6f5543"
                  strokeOpacity="0.36"
                  strokeWidth="1"
                  x1={plot.left - 4}
                  x2={plot.left}
                  y1={tick.screen}
                  y2={tick.screen}
                />
                <text
                  data-axis-label="y"
                  fill="#6f5a49"
                  fillOpacity="0.88"
                  fontFamily="ui-monospace, SFMono-Regular, Menlo, Consolas, monospace"
                  fontSize="9.5"
                  fontWeight="600"
                  textAnchor="end"
                  x={plot.left - 7}
                  y={tick.screen + 3.2}
                >
                  {formatAxisValue(tick.value)}
                </text>
              </g>
            ))}
          </g>
        </svg>

        <div className="pointer-events-none absolute left-4 top-4 flex max-w-[70%] flex-wrap items-center gap-2">
          {searchActive ? (
            <span className="rounded-full border border-copper-400/25 bg-ink-800/95 px-3 py-1 text-[11px] font-medium text-copper-200 shadow-sm">
              {matchCount > 0
                ? `${matchCount} matching node${matchCount === 1 ? "" : "s"}`
                : "No matching nodes"}
            </span>
          ) : (
            <span className="rounded-full border border-warm-100/15 bg-ink-800/90 px-3 py-1 text-[11px] text-parchment-400 shadow-sm">
              Drag to pan · Scroll to zoom · Hover for detail
            </span>
          )}
          {visibleClusters.length === 0 && (
            <span className="rounded-full border border-amber-400/25 bg-amber-400/10 px-3 py-1 text-[11px] text-amber-200">
              No clusters match the current filter
            </span>
          )}
        </div>

        <div className="absolute right-4 top-4 flex flex-col gap-1.5">
          {onToggleFullscreen && (
            <button
              aria-label={fullscreen ? "Exit fullscreen" : "Enter fullscreen"}
              className="h-8 rounded-lg border border-warm-100/20 bg-ink-800/95 px-2 text-[10px] font-semibold tracking-wide text-parchment-200 shadow-sm transition-colors hover:border-copper-400/30 hover:bg-parchment-50/10"
              onClick={onToggleFullscreen}
              title={fullscreen ? "Exit fullscreen (Esc)" : "Fullscreen graph"}
              type="button"
            >
              {fullscreen ? "EXIT" : "FULL"}
            </button>
          )}
          <button
            aria-label="Zoom in"
            className="h-8 w-8 rounded-lg border border-warm-100/20 bg-ink-800/95 text-lg leading-none text-parchment-200 shadow-sm transition-colors hover:border-copper-400/30 hover:bg-parchment-50/10 disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:border-warm-100/20 disabled:hover:bg-ink-800/95"
            disabled={!canZoomIn}
            onClick={() => zoomBy(1.32)}
            title={canZoomIn ? "Zoom in" : "Maximum zoom reached"}
            type="button"
          >
            +
          </button>
          <button
            aria-label="Zoom out"
            className="h-8 w-8 rounded-lg border border-warm-100/20 bg-ink-800/95 text-lg leading-none text-parchment-200 shadow-sm transition-colors hover:border-copper-400/30 hover:bg-parchment-50/10 disabled:cursor-not-allowed disabled:opacity-35 disabled:hover:border-warm-100/20 disabled:hover:bg-ink-800/95"
            disabled={!canZoomOut}
            onClick={() => zoomBy(1 / 1.32)}
            title={canZoomOut ? "Zoom out" : "Minimum zoom reached"}
            type="button"
          >
            −
          </button>
          <button
            aria-label="Fit to screen"
            className="h-8 rounded-lg border border-warm-100/20 bg-ink-800/95 px-2 text-[10px] font-semibold tracking-wide text-parchment-200 shadow-sm transition-colors hover:border-copper-400/30 hover:bg-parchment-50/10"
            onClick={fitAll}
            title="Fit to screen"
            type="button"
          >
            FIT
          </button>
          <button
            aria-label="Reset view"
            className="h-8 rounded-lg border border-warm-100/20 bg-ink-800/95 px-2 text-[10px] font-semibold tracking-wide text-parchment-200 shadow-sm transition-colors hover:border-copper-400/30 hover:bg-parchment-50/10"
            onClick={() => {
              onClearSelection();
              fitAll();
            }}
            title="Reset view and clear selection"
            type="button"
          >
            RESET
          </button>
        </div>

        <div className="pointer-events-none absolute bottom-4 right-4 rounded-full border border-warm-100/15 bg-ink-800/90 px-2.5 py-1 font-mono text-[10px] text-parchment-400 shadow-sm">
          {Math.round(view.scale * 100)}%
        </div>

        {hovered && (hoveredFolio || hoveredCluster) && (
          <div
            className="pointer-events-none absolute z-20 rounded-xl border border-warm-100/15 bg-ink-800/[0.98] p-3.5 text-[11px] shadow-2xl ring-1 ring-ink-950/30 backdrop-blur-sm"
            style={{
              left: tooltipLeft,
              top: tooltipTop,
              width: tooltipWidth,
            }}
          >
            {hoveredFolio ? (
              <FolioTooltipContent folio={hoveredFolio} />
            ) : hoveredCluster ? (
              <ClusterTooltipContent cluster={hoveredCluster} />
            ) : null}
          </div>
        )}
      </div>
    );
  },
);

export default BenchmarkGraph;
