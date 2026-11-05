# Milestone 3 notes

## Scope delivered

Milestone 3 adds a local benchmark mapping review screen, a local CSV/XLSX
benchmark-level importer, SQLite storage for both, and per-folio benchmark
comparison. It does not add the benchmark cluster graph, web search, AI/Ollama,
voice, authentication, cloud deployment or any remote benchmark download.

## Mapping review

- Every imported scheme is listed with its original name, normalized name,
  current benchmark and review status.
- Automatic keyword suggestions are saved as `needs_review`.
- Approving the current suggestion or choosing another benchmark saves the row
  as `reviewed`, with source `manual`, in `scheme_benchmarks`.
- Reviewed mappings are preserved across later snapshot imports by matching the
  normalized scheme name. A new snapshot does not silently reset a user review.
- The mapping form only accepts configured benchmark names or benchmark names
  that already have local levels. This prevents free-text mappings that could
  never be compared.

APIs:

- `GET /api/v1/benchmark-mappings`
- `PATCH /api/v1/benchmark-mappings/{scheme_id}` with
  `{"benchmark_name": "Nifty 50 TRI"}`

## Benchmark level storage

The new `benchmark_levels` table stores one positive closing level per
normalized benchmark name and date. It also records the source file name and
import timestamp. The original uploaded file is not retained.

Accepted layouts:

- long: `benchmark_name, date, level`
- wide: `date, <benchmark 1>, <benchmark 2>, ...`

CSV and XLSX are supported. The importer detects the header row, accepts the
configured date formats, skips invalid rows with warnings, and updates existing
benchmark/date values. It never interpolates or fetches prices.

APIs:

- `GET /api/v1/benchmarks/levels`
- `POST /api/v1/benchmarks/levels/import` with a multipart `file` field

Demo levels: `samples/benchmark_levels/demo_benchmark_levels.csv` (78 levels,
six benchmark series, covering the demo transaction and valuation dates).

The old `config/benchmark_reviews.yaml` and `config/benchmark_levels.yaml` files
are retained only as legacy notes and are ignored by the application.

## Comparison rules

- **Lump sum:** one `purchase` flow, no SIP, switch or redemption. Compare folio
  absolute return with benchmark point-to-point return from the purchase date to
  the valuation date.
- **SIP / multiple flows / redemption / switch:** apply the same dated cash flows
  to the benchmark level series, calculate benchmark XIRR, and compare it with
  folio XIRR.
- **Difference** = folio return/XIRR − benchmark return/XIRR. Positive is
  outperformance, negative is underperformance.
- Missing mappings, unreviewed mappings, missing levels, missing cash-flow
  dates, missing valuation-date levels and unsolvable returns all produce
  **Not available** with a specific reason.
- Levels are matched by normalized benchmark name, so capitalization and
  punctuation differences do not create duplicate series.

## UI

- Added an app header navigation between **Dashboard** and **Benchmark Mapping
  & Data**.
- Added `apps/web/src/app/benchmarks/page.tsx` and
  `BenchmarkClient.tsx` with summary cards, searchable/status-filtered mapping
  rows, per-row approval/save, level upload, import warnings and stored-series
  coverage.
- The folio table now shows folio absolute return and XIRR neutrally, benchmark
  return/XIRR with method, comparison status, and a separate difference column.
- Green is used only for a positive difference (folio ahead); red only for a
  negative difference (folio behind); amber is used for review, missing mapping
  and missing-level states.

## Tests added

`apps/api/tests/test_milestone3.py` covers:

- correct mapping update and badge removal;
- validation for unknown benchmark names and missing schemes;
- missing benchmark mapping;
- missing benchmark levels;
- lump-sum point-to-point comparison;
- SIP comparison using the same dated cash flows and benchmark XIRR;
- redemption/switch cash-flow comparison on both switch legs;
- benchmark levels not covering the valuation date;
- a missing SIP cash-flow date;
- invalid/missing benchmark dates and invalid levels;
- wide-layout CSV and XLSX level files;
- reviewed mappings surviving snapshot re-import.

The Milestone 2 benchmark tests were updated to use the SQLite mapping and level
APIs instead of the removed YAML review/level hooks.

## Verification

- Backend suite: **51 passed**.
- Frontend production build: passes (`npm run build`, Next.js 16).
- Browser verification:
  - empty dashboard and empty benchmark page render;
  - demo load shows 14 schemes: 13 automatic **Needs Review** and one
    **Needs mapping**;
  - sample level upload stores 78 levels across six series;
  - approving a mapping removes the badge and updates the dashboard;
  - changing an unmapped scheme to **Nifty 50 TRI** saves a manual review;
  - reviewed demo folios show point-to-point benchmark returns and a red/green
    difference; unreviewed folios show **Mapping needs review** and **Not
    available**.

## Known limitations

- Benchmark comparisons use only the dates present in the local level file.
  Gaps are reported, not filled.
- A mapping can only be saved to a benchmark already configured or present in
  local levels.
- The existing benchmark categories are keyword suggestions, not a full
  industry classification. Every one still requires local review.
- The benchmark graph is intentionally not implemented until Milestone 4.
