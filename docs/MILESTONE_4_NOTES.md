# Milestone 4 notes

## Scope delivered

Milestone 4 adds a local **Benchmark Cluster Graph** over the existing
Milestone 3 snapshot and comparison data. It provides benchmark nuclei,
connected folio nodes, zoom/pan/reset, search highlighting, performance/
benchmark/client filters, benchmark summaries and the shared folio detail
popup. It is designed to stay readable with 200+ folios.

It does not add live or web benchmark fetching, NAV history, AI/Ollama, voice,
authentication, cloud deployment or any new return/XIRR calculation. The graph
is read-only and does not modify mappings, levels, folios or snapshots.

## Read model and API

`apps/api/src/mfd_dashboard/benchmark_graph.py` builds the graph from
`get_dashboard(db)`. It reuses the dashboard's existing folio comparison
results rather than recalculating returns or XIRR.

API:

- `GET /api/v1/benchmark-graph`

The response contains:

- benchmark clusters with display name, review state, level/comparison counts,
  aggregate ahead/behind/not-available/review counts and average difference;
- folio nodes with client, scheme, benchmark, comparison fields and performance
  state;
- cluster connections (each folio belongs to exactly one benchmark nucleus);
- summary counts and local benchmark-coverage notes.

Clusters include every configured or imported benchmark, even with zero folios.
`Other / Unmapped` is added only when at least one folio is mapped to it.

## Node states

| State | Meaning | Colour |
| --- | --- | --- |
| `ahead` | Available comparison; folio difference is positive | Green |
| `behind` | Available comparison; folio difference is negative | Red |
| `in_line` | Available comparison; difference is zero | Slate |
| `needs_review` | Mapping missing/needs review, or required levels missing | Amber |
| `not_available` | Other unavailable comparison, including missing folio AUM | Grey |

Missing mappings, levels, transaction dates, folio AUM or unsolvable returns
are reported as review or unavailable states. They are never repaired,
estimated or silently treated as zero. Green and red are used only for
performance states; ordinary UI actions do not use them.

## Layout and interactions

- `apps/web/src/lib/graphLayout.ts` places benchmark nuclei on a compact
  deterministic grid and folios in concentric rings. There is no external graph
  library and no random force simulation, so the same data always produces the
  same layout.
- `BenchmarkGraph.tsx` renders one SVG with pan, wheel zoom, +/− zoom, FIT and
  Reset view. Zoom is clamped between 12% and 400%.
- Folio labels are hidden when many nodes are visible; they appear on hover, on
  a match/selection, or when zoomed in. This keeps large graphs readable.
- A resize fallback measures the container explicitly and on
  `visibilitychange`/`resize`, so a graph mounted in a background tab still
  fits when first shown.
- Clicking a nucleus focuses its cluster and opens the benchmark summary.
  Clicking a folio opens the shared `FolioDetailDialog` also used by the
  dashboard table.
- Search uses `useDeferredValue`, matches benchmark names, clients, folio
  numbers and scheme names, highlights matches with a focus ring, and dims but
  does not hide non-matching nodes.
- Performance, benchmark and client filters only hide non-matching folios;
  nuclei stay visible. Search can be applied together with filters.

## UI files

- `apps/web/src/app/graph/page.tsx`
- `apps/web/src/components/BenchmarkGraph.tsx`
- `apps/web/src/components/BenchmarkGraphClient.tsx`
- `apps/web/src/components/BenchmarkGraphInspector.tsx`
- `apps/web/src/components/FolioDetailDialog.tsx`
- `apps/web/src/lib/graphLayout.ts`
- `apps/web/src/components/FolioTable.tsx` (shared popup plus **View** column)
- `apps/web/src/components/AppNav.tsx` (graph navigation link)

## Tests

`apps/api/tests/test_milestone4.py` covers:

- empty graph with all six configured benchmarks and zero folios;
- demo clusters, cluster connections and `Other / Unmapped`;
- green/red/grey states, missing folio AUM and cluster averages;
- amber `needs_review` for mapping-required and levels-missing cases;
- 220 synthetic folios with graph creation under 10 seconds.

Run the full backend suite:

```powershell
cd "C:\Users\ariji\Desktop\Shontu AI\mfd-dashboard"
.\.venv\Scripts\python.exe -m pytest -q apps/api
```

## Browser verification

- Empty snapshot: **6 nuclei**, **0 folios**, no console errors.
- Demo snapshot without reviewed mappings: **7 nuclei**, **14 amber folios**.
- Demo with sample levels and 13 approved mappings: **2 green (ahead)**,
  **10 red (behind)**, **1 grey (F010, missing folio AUM)** and
  **1 amber (unmapped scheme)**.
- Nucleus click opens the benchmark summary with counts, average performance,
  level/comparison coverage and cluster folios.
- Folio click opens the shared detail popup with client, folio number,
  benchmark, scheme, invested amount, folio AUM, holding period, absolute
  return, XIRR, benchmark value, difference, method and review reason.
- Search for `Meera` reported **2 matching nodes** (Nifty 50 nucleus and F007),
  highlighted both and dimmed the rest without removing nodes.
- Benchmark filter `Nifty 50 TRI` showed 3 of 14 folios; client filter
  `Meera Iyer` showed 1 of 14; performance filter `underperforming` showed
  0 folios while all 7 nuclei stayed visible.
- Zoom changed 78% → 103%; pan moved the graph; FIT/Reset returned it to 78%.
- A temporary 224-folio dataset rendered **231 nodes** (7 nuclei + 224 folios)
  at a fitted 53% scale, with folio labels suppressed for readability. The
  temporary rows were removed after verification.
- No browser console errors were observed during the checks.

## Known limitations

- Positions are deterministic but not optimised for avoiding every label or
  node collision at extreme zoom levels.
- Folio labels are intentionally suppressed in large graphs; hover or zoom in
  to identify a node.
- The graph does not aggregate by client or scheme beyond the current filters.
- A folio can appear in only one benchmark cluster, following the single active
  scheme mapping.
- The graph display depends on reviewed mappings and local benchmark levels.
  Missing review/level data is shown as amber or grey, never filled in.
- The graph is local-only and not intended for export or cloud sharing.
