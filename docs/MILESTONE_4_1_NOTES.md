# Milestone 4.1 — Graph readability and UI polish

Status: implemented, built and browser-verified. Awaiting approval before
Milestone 5.

## Scope

This milestone changes presentation only. It does not change the database
schema, importer, transaction calculations, XIRR calculations, benchmark
comparison logic, APIs or stored data. No web search, AI/Ollama, voice,
authentication, cloud deployment, live benchmark fetching or new pages were
added.

## Graph changes

### Benchmark nuclei

- Remain visible even with zero folios.
- Show the benchmark name, folio count, a compact state summary
  (`2 ahead · 1 behind · 1 not available · 1 review`) and the average
  comparison difference when available.
- Use the sky-blue nucleus style, larger than folio nodes, with a subtle halo
  and dashed cluster boundary.

### Folio labels

- Primary label: client name.
- Secondary label: scheme name, shown when there is room at closer zoom.
- The folio number (`F006`) is shown in the hover tooltip and the detail popup.
- Long names are truncated with an ellipsis. Full values remain available in
  tooltips.
- Labels are positioned on the preferred side of the node, with fallbacks to the
  opposite side, below and above. A collision check against other labels,
  nucleus labels and node dots prevents bad overlap.
- Label density is intentionally tiered:
  - small graphs at fitted zoom: client names;
  - closer zoom: client plus scheme names;
  - very large graphs at fitted zoom: cluster labels and hover/zoom for
    individual folios;
  - search matches, the selected node and the hovered node keep their labels.
- If a full two-line label cannot fit, the client name is still placed even if
  the scheme name must wait for more room.

### Hover tooltips

Dark, non-interactive tooltips (`pointer-events: none`) show:

- Folio: client, folio number, scheme, benchmark, current value, absolute
  return, XIRR, benchmark return/XIRR, difference, status and a comparison note
  when unavailable.
- Benchmark: name, folio count, ahead, behind, not available, needs review and
  average folio performance versus benchmark.

Tooltips are positioned inside the graph and flip away from the right/bottom
edge.

### Navigation and layout

- Larger, deterministic cluster spacing.
- Folio nodes smaller than benchmark nuclei.
- Subtle status-coloured links.
- Smooth wheel zoom, drag-to-pan and eased programmatic zoom/fit.
- `+` / `−`, `FIT` (fit to screen) and `RESET` (clear selection and fit)
  controls.
- `Fit to screen` and `Reset view` are also available in the filter status row.
- A hidden/background-tab fallback applies the fitted view immediately so the
  graph does not start at 100% in a background tab.

## UI polish

- Consistent panel borders, softer card shadows, calmer background.
- Consistent focus rings, button hover/active states and short transitions.
- Better empty states for client and folio tables and an empty graph filter
  state with a clear-filters action.
- Table headers, row hover states and count badges clarified.
- `Matched`, `Required columns found` and `Comparisons ready` no longer use
  green. Green is reserved for “folio ahead of benchmark”; red for “folio behind
  benchmark”; amber for review; grey for unavailable; sky blue for benchmarks
  and neutral actions.

## Files changed

- `apps/web/src/components/BenchmarkGraph.tsx`
- `apps/web/src/lib/graphLayout.ts`
- `apps/web/src/components/BenchmarkGraphClient.tsx`
- `apps/web/src/components/BenchmarkGraphInspector.tsx`
- `apps/web/src/components/DashboardClient.tsx`
- `apps/web/src/components/FolioTable.tsx`
- `apps/web/src/components/ClientSummaryTable.tsx`
- `apps/web/src/components/ReconciliationPanel.tsx`
- `apps/web/src/components/PreviewPanel.tsx`
- `apps/web/src/components/UnmatchedPortfolioPanel.tsx`
- `apps/web/src/app/globals.css`
- `apps/web/tailwind.config.ts`
- `README.md`
- `docs/MILESTONE_4_1_NOTES.md`

No backend code, API schema, importer or calculation file was changed.

## Verification

### Build and tests

- `npm run build` in `apps/web`: passed, TypeScript passed, routes `/`,
  `/benchmarks`, `/graph`.
- `.\.venv\Scripts\python.exe -m pytest apps/api`: **56 passed**.

### Demo browser verification

After loading the demo snapshot, importing
`samples/benchmark_levels/demo_benchmark_levels.csv` and approving the 13 real
benchmark mappings:

- 7 nuclei, 14 folio nodes.
- 2 ahead, 10 behind, 1 not available (F010 missing AUM), 1 needs review.
- Fitted view showed all 14 client names; scheme names were suppressed.
- At ~129–170% zoom, all 14 client names and 12 of 14 scheme names showed; the
  remaining scheme labels were held back by collision detection rather than
  overlapping.
- Folio hover for Kabir Nair / F006 / Apex Flexi Cap Fund showed current value
  ₹1,20,000, absolute return +4.35%, XIRR +1.01%, benchmark XIRR +8.85%,
  difference −7.84% and status “Behind benchmark”.
- Benchmark hover for Nifty 500 TRI showed 2 folios, 0 ahead, 2 behind, 0 not
  available, 0 review and average −7.16%.
- Clicking the Kabir Nair node opened the shared folio detail popup with the
  correct client, folio, scheme, benchmark and comparison values.
- Search for `Meera` highlighted the Nifty 50 nucleus and the Meera Iyer folio,
  moved them into view and dimmed other nodes without hiding them.
- Benchmark filter `Nifty 50 TRI` showed 3 folios with all nuclei retained.
- Client filter `Meera Iyer` showed 1 folio.
- Underperforming filter showed 0 folios while all nuclei remained visible.
- `FIT` restored the fitted view.

### 200+ folio verification

A temporary dataset with **224 folios** (210 synthetic copies plus the 14 demo
folios) produced **231 nodes** (7 nuclei + 224 folios). The fitted view rendered
at about 31% with cluster labels visible and folio labels suppressed for
density; zooming in revealed client and scheme labels with collision handling.
`FIT` returned to 31%. The temporary rows were removed and the database was
restored to the 14-folio demo snapshot.

No browser console errors were observed.

## Known limitations

- At very high node density, collision detection intentionally withholds some
  secondary scheme labels. Hovering always shows the full scheme and folio
  detail.
- The graph is a read-only presentation layer. It does not repair missing
  mappings, levels or folio AUM.
- No visual screenshot verification was possible in the background browser
  tab; DOM text, node counts, zoom transforms, tooltip contents and clicks were
  verified directly.
