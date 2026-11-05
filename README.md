# MFD Portfolio Dashboard

A local, privacy-first dashboard for a mutual fund distributor (MFD). It is a
separate project and does not modify or depend on the existing `fund-engine`
repository.

**Milestone 6 scope:** simplify the user-facing app to one workflow:
**Upload → Benchmark Data → Graph**. The landing page now contains only the app
title, three navigation links, current snapshot status, basic warnings and the
four-file upload. The old KPI cards, client/folio tables, Business Review,
concentration charts and other analytical panels are no longer shown. The
`/business-review` route remains as an inactive placeholder so old bookmarks do
not break, while its backend endpoint, calculations and tests are unchanged.

The warm graphite identity, copper primary actions and semantic performance
colours are retained. The Benchmark Cluster Graph is the main screen. Its canvas
is a softer, less saturated peach with a proper coordinate grid: thin X/Y axes,
low-contrast major and minor gridlines, and minimal numeric tick labels. The grid
is derived from the same pan/zoom transform as the nodes, so it moves and rescales
with the graph instead of sitting behind it as a static pattern. The deterministic
organic cluster layout, client-first labels, search, filters, tooltips, folio
popup, zoom, pan, fit/reset and 200+ folio support remain in place. Every visible
control is functional or disabled with an explanatory browser tooltip.

**Milestone 6.1 scope:** replace the decorative background pattern with a
view-driven chart grid. The X axis sits at the bottom of the plot area and the Y
axis on the left. Gridlines, ticks and coordinate labels are recalculated from
the current pan/zoom transform; zooming in refines the grid, zooming out reduces
its density, and panning shifts it with the nodes. Axis and label styling stays
subtle so nodes and client names remain the primary focus.

**Milestone 7 scope:** make the workflow reliable with real InvestWell files.
Uploads are streamed from temporary local files instead of being kept in API
memory. XLSX workbooks are opened read-only, CSV rows are streamed, and the
browser receives a compact preview containing counts, file-level diagnostics,
skipped-row reasons and at most 200 issues. Each file is limited to **25 MB**
and **100,000 data rows**; an XLSX may not expand beyond **256 MB**. Blank,
total, duplicate and incomplete rows are skipped with a counted reason, while
invalid dates and amounts are retained but excluded from calculations and shown
as **Not available**. Benchmark Data now reports which schemes still need
mapping or review, which series have no local levels, whether the valuation date
and first transaction date are covered, and the exact missing comparison dates.
Missing levels are never interpolated or estimated. The graph explains every
colour and points to the exact missing dates.

**Milestone 7 feedback:** the Benchmark Cluster Graph has a fullscreen workspace
that keeps search, filters, zoom, fit/reset, tooltips and the folio popup while
covering the viewport. Benchmark Data now supports practical bulk work:
scheme-level selection, applying one benchmark to many schemes at once,
accepting visible automatic suggestions, keyword rules with a mandatory preview,
and CSV/XLSX export/import of the scheme mapping table. The benchmark dropdowns
use the full NSE equity master list (145 TRI indices as of September 2026), so
every benchmark is selectable even without local level data. Every bulk action
reports how many schemes and folios changed and how many folios moved out of
**Other / Unmapped**. Invalid imports are validated and rejected before saving,
and all mappings remain reviewable in the scheme table.

Milestone 3 included importing the four InvestWell exports (Client Details,
Folios, Portfolio Valuation and Transaction Statement), storing a local SQLite
snapshot, calculating folio-level invested amounts, holding period, absolute
return and XIRR from dated transactions, reviewing benchmark mappings locally,
importing local benchmark closing levels, comparing each folio with its
benchmark, and showing reconciliation warnings and import issues.

Not included: live benchmark or web search, NAV-history downloads, AI/Ollama,
voice, authentication, cloud deployment, or automatic benchmark fetching. The
graph uses only the existing local snapshot and comparison results; it adds no
new return, XIRR or benchmark calculation.

## Privacy

- The API binds to `127.0.0.1` in the commands below. It is not exposed to the
  network.
- Client data is stored only in `data/local/` on this laptop.
- PAN, Aadhaar, email, phone, address, bank, KYC, nominee and similar columns
  are ignored. They are reported as “ignored sensitive columns” in the preview
  and are never stored.
- The original uploaded `.xlsx` and `.csv` files are written only to a
  temporary folder under `data/local/uploads/` while preview runs. The folder is
  deleted when that request finishes. Only normalized, whitelisted values are
  written to the local database and preview JSON.
- There are no outbound API calls. Benchmark mappings and closing levels are
  stored in local SQLite. The legacy YAML files are ignored.

## Requirements

- Windows PowerShell
- Python 3.11 or newer
- Node.js 20.9 or newer and npm

The project was tested with Python 3.13 and Node.js 24, using Next.js 16 and
React 19. The backend uses `openpyxl` to read `.xlsx` files and Python's
built-in `csv` reader for `.csv` files.

## First-time setup

Open PowerShell in the project folder:

```powershell
cd "C:\Users\ariji\Desktop\Shontu AI\mfd-dashboard"

python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r apps/api/requirements.txt

cd apps\web
npm install
```

## Run the app

The simplest path is one PowerShell terminal from the project root:

```powershell
cd "C:\Users\ariji\Desktop\Shontu AI\mfd-dashboard"
.\start.ps1
```

Then open **http://127.0.0.1:3000**. The backend runs at
`http://127.0.0.1:8000`; API documentation is at
`http://127.0.0.1:8000/docs`.

To run the two processes manually, use two PowerShell terminals.

### Terminal 1 — backend

```powershell
cd "C:\Users\ariji\Desktop\Shontu AI\mfd-dashboard"
.\.venv\Scripts\Activate.ps1
python -m uvicorn mfd_dashboard.main:app --app-dir apps/api/src --host 127.0.0.1 --port 8000 --reload
```

### Terminal 2 — frontend

```powershell
cd "C:\Users\ariji\Desktop\Shontu AI\mfd-dashboard\apps\web"
npm run dev
```

## What should appear in the browser

The main navigation contains only **Upload**, **Benchmark Data** and **Graph**.
On the first visit the snapshot is empty. Use one of two paths:

1. Click **Load demo data** to load the synthetic four-file snapshot.
2. Upload the four real InvestWell files and confirm the preview.

There are no KPI-card grids, client/folio tables, concentration charts or
Business Review panels on the landing page. The page answers only: “Is my data
imported, and can I open the graph?”

### Visual identity and controls

- Surfaces use a warm graphite/charcoal base, parchment text, copper primary
  actions and links, warm borders, sage as a restrained secondary accent, and a
  soft peach graph canvas. Navy and slate-blue are not used as the main identity.
- Performance colours are semantic only: **emerald** for ahead, **rose** for
  behind, **amber** for review/warning, and **grey** for unavailable or neutral.
  Ordinary primary buttons and navigation use copper, never green.
- Glass blur is deliberately limited to the top navigation, snapshot and graph
  summary cards, the shared folio dialog, and the graph inspector. Standard
  panels remain solid dark surfaces.
- Every visible control is audited. Disabled controls explain the reason in a
  browser tooltip, for example missing files, unchanged mappings, failed preview
  readiness, unavailable graph zoom limits, or filters that are already clear.
  Non-interactive cards do not show a hover treatment that implies clicking.

### Demo snapshot

After clicking **Load demo data**, the Upload page should show:

- **Snapshot ready** and **Graph available**, with valuation date
  **27 Oct 2026**.
- Compact status values: **11 clients**, **14 folios**, **20 transactions**,
  reviewed benchmark mappings, and the number of folios with a local benchmark
  comparison. These are inline status values, not a KPI-card grid.
- **Needs attention** for the remaining amber mapping, the unmatched folio and
  the reconciliation warning.
- Buttons to **Open Graph** and open **Benchmark Data**.

On a fresh demo, automatic mappings start amber and comparisons start at zero.
Import `samples/benchmark_levels/demo_benchmark_levels.csv` and approve the 13
automatic mappings to reach **13 reviewed**, **1 needs review** and **12
comparisons ready**. The current local demo database already has those reviews
and 78 benchmark levels loaded.

The graph then shows **7 nuclei** and **14 folios**: **2 ahead**, **10 behind**,
**1 not available** (F010 has no folio AUM) and **1 needs review** (the unmapped
scheme). Benchmark comparisons are never invented; a folio remains
**Not available**, **Needs Review**, **Mapping needs review**, **Needs mapping**
or **Levels missing** until its mapping is approved and the required local
levels exist.

### Benchmark Data screen

Use the **Benchmark Data** link in the main navigation (or open
`http://127.0.0.1:3000/benchmarks`).

1. **Review scheme mappings.** Every scheme is listed with its original name,
   normalized name, folio count, current benchmark mapping, suggestion and review
   status. Automatic suggestions start amber as **Needs Review**; a scheme with no
   automatic category starts as **Needs mapping**. When a suggestion exists, the
   row shows the exact benchmark and the keyword that produced it, with a **Use
   suggestion** link. Mapping is scheme-level: saving a benchmark applies it to
   every folio of that scheme.
2. Choose a different benchmark from the row dropdown and click
   **Approve / Save**. The dropdown lists the full NSE equity benchmark master
   list from `config/benchmark_master.yaml`, including benchmarks with no local
   levels yet. Approving the current suggestion also works. The row changes to
   **Reviewed** and the amber badge disappears. The change is saved in SQLite
   and survives later snapshot imports. Each row also shows its date coverage
   state and how many required dates are missing.
3. **Bulk mapping.** Tick the checkbox on one or more rows (or use **Select
   filtered** / the header checkbox), choose a benchmark in the bulk toolbar and
   click **Apply to selected**. The toolbar states how many schemes and folios
   are affected, and the success notice reports how many folios moved out of
   **Other / Unmapped** and how many remain unmapped. **Accept suggestions**
   approves only suggestions that are already visible: all of them, or only the
   selected schemes when a selection exists.
4. **Keyword rules.** Enter a keyword and a benchmark, then click **Preview
   matches**. The preview lists every matching scheme with its folio count and
   current mapping, and states how many folios would move out of **Other /
   Unmapped**. Nothing is saved until **Apply rule** is clicked; applying a rule
   overwrites matched schemes, including reviewed ones, and remains editable in
   the table.
5. **Export / import mappings.** **Export CSV** or **Export XLSX** downloads one
   row per scheme with `scheme_id`, `scheme_name`, `normalized_scheme_name`,
   `benchmark_name`, `review_status`, `folio_count` and `source`. To import,
   choose the file and click **Validate file**. Validation runs before any save
   and reports row-level errors, warnings, unchanged rows and the exact schemes
   and folios that would change. **Apply validated changes** is disabled while
   any error exists; applying an invalid file is rejected by the API with HTTP
   400 and saves nothing. Re-importing an unchanged export makes no changes. A
   row becomes a change only when its **benchmark_name** differs or its
   **review_status** is explicitly set to `reviewed`; unknown schemes or
   benchmarks that are not available locally are rejected.
6. **Review the required date coverage.** The coverage panel lists every
   benchmark series used by a reviewed mapping. For each series it shows the
   number of required dates, whether the valuation date is covered, whether each
   scheme's first transaction date is covered, and the exact missing dates. A
   scheme with no dated transactions is marked **No transactions** rather than
   guessed. **Missing dates** or **No local levels** means the comparison stays
   **Not available** until those dates are added.
7. **Import local benchmark levels.** Choose a `.csv` or `.xlsx` file and click
   **Import benchmark levels**. The file limit is **25 MB**. The page reports
   new/updated/skipped rows and shows the stored series with date coverage.
8. To try the demo, upload
   `samples/benchmark_levels/demo_benchmark_levels.csv`. It contains 78 levels
   for six benchmark series covering the demo transaction dates and the
   **27 Oct 2026** valuation date.
9. After a mapping is reviewed and levels cover every required date, the
   benchmark graph and folio popup show the benchmark return/XIRR and difference.
   - **Point-to-point absolute return** is used for a single purchase with no
     SIP or switch.
   - **Same-dated cash-flow XIRR** is used for SIPs, multiple purchases,
     redemptions and switches.
   - Green difference = folio ahead; red = folio behind; amber = review or
     missing dates; **Not available** = missing mapping, levels or a return that
     cannot be calculated.
10. For example, after loading the demo, importing the sample level file and
    approving **Apex Blue Chip Advantage Fund** and **Apex Unknown Sector Fund**
    to **Nifty 50 TRI**, those two folios show comparisons. The other 12 folios
    remain **Not available** until their mappings are reviewed and levels exist
    for their benchmark and dates.

### Benchmark Cluster Graph

Open **Graph** in the main navigation or `http://127.0.0.1:3000/graph`.

- The graph canvas uses a softer, less saturated warm peach/blush tint with a
  real coordinate grid. The **X axis** runs along the bottom of the plot area and
  the **Y axis** along the left. Thin warm-brown/grey major and minor gridlines
  form the chart cells, with minimal monospace numeric tick labels. The axes are
  the fixed chart frame; ticks, labels and gridlines are derived from the current
  transform. Gridlines move with the nodes when panning and scale with them when
  zooming. Zooming in introduces finer grid steps, while zooming out reduces grid
  density. Low opacity keeps the grid behind the nodes, labels and tooltips.
- Every configured or imported benchmark is shown as a dark-bronze **nucleus**
  on the canvas, even when no folio is mapped to it. Its light label card uses
  dark text and shows the benchmark name, folio count, a short status summary
  such as “2 ahead · 1 behind · 1 not available”, and the average comparison
  difference when one is available.
- Smaller connected nodes are folios. Colours reuse the existing comparison
  result and the graph header explains them:
  - **Green = Ahead** of the benchmark.
  - **Red = Behind** the benchmark.
  - **Grey = Not available.** The folio has no dated transactions, no current
    value, or a return/XIRR that cannot be calculated from the supplied values.
  - **Amber = Needs review.** The mapping is missing or not approved, or a
    reviewed mapping is still missing one or more local benchmark dates.
  - Select a folio to see the exact reason. When local levels are missing, the
    folio popup and graph tooltip name the missing dates; the full exact list is
    on **Benchmark Data**. Missing levels are never filled in by interpolation.
- **Folio labels** use the client name as the primary label. At closer zoom the
  scheme name appears underneath; long names are truncated with an ellipsis and
  the full values are always available in the hover tooltip. Collision
  detection keeps labels apart. At fitted/low zoom on a large graph, secondary
  labels are suppressed first; with 200+ folios the graph shows the clusters and
  uses hover/zoom to reveal individual labels.
- **Hover tooltips** summarise a folio’s client, folio number, scheme, benchmark,
  current value, absolute return, XIRR, benchmark return/XIRR, difference and
  status. Benchmark tooltips show folio count, ahead/behind/not available/review
  counts and average folio performance. Tooltips are non-interactive and never
  block clicking.
- With the demo snapshot, the graph shows **7 nuclei** (six configured
  benchmarks plus **Other / Unmapped**) and **14 folios**. Before mappings are
  reviewed, all 14 folios are amber. After importing
  `samples/benchmark_levels/demo_benchmark_levels.csv` and approving the 13
  automatic mappings, the demo shows **2 ahead**, **10 behind**, **1 not
  available** (F010 has no folio AUM) and **1 needs review** (the unmapped
  scheme).
- Click a nucleus to open its summary: folio count, ahead/behind/not available/
  review counts, missing-AUM count, average folio and benchmark performance,
  local level coverage, comparison methods, and the folios in that cluster.
- Click a folio node to open the shared **Folio detail** popup. It includes
  client, folio number, scheme, benchmark,
  invested amount, folio AUM, holding period, absolute return, XIRR, benchmark
  return/XIRR, difference, comparison method and any review reason.
- **Search** highlights matching benchmark names, clients, folio numbers and
  schemes, draws a focus ring around matches, and moves them into view. Other
  nodes stay visible but dimmed; nothing is deleted or hidden by search.
- **Performance** filters: all, outperforming, underperforming, not available
  and needs review. **Benchmark** filters by category or benchmark, and
  **Client** filters by client. Filtering hides non-matching folios only;
  benchmark nuclei remain visible so empty categories are still identifiable.
- **Zoom in / Zoom out**, the mouse wheel, **FIT** and **RESET** control the view.
  Drag anywhere in the graph to pan. The coordinate grid and nodes share the same
  transform, so panning shifts both together and zooming scales both together.
  **Fit to screen** keeps the current selection and restores the fitted grid;
  **Reset view** clears the selection, closes an open folio popup and restores
  the fitted view. Programmatic zoom and fit transitions are short and eased.
  Zoom buttons disable themselves at the minimum and maximum scale and explain
  the limit on hover.
- **Fullscreen** opens the graph workspace over the whole viewport, including
  the search box, performance/benchmark/client filters, zoom, **FIT**, **RESET**,
  tooltips and the folio popup. Use the **Fullscreen** button in the controls or
  **FULL** on the canvas, then **Exit fullscreen**, **EXIT** or **Esc** to
  return. The browser Fullscreen API is used when available, with a CSS
  fixed-overlay fallback; the canvas re-measures on resize so the peach canvas,
  coordinate grid and layout stay responsive.
- The layout is deterministic and local: benchmark nuclei use a golden-angle
  seed followed by force relaxation and label-aware collision separation, while
  folios stay in concentric rings around their own nucleus. Spacing accounts for
  both node size and label-card width, so clusters remain grouped, stable and
  readable. The same snapshot always produces the same layout, filtering never
  moves nodes, and 200+ folios remain navigable. Scheme labels appear only at
  closer zoom, and client labels use dark text or dark outlines on the peach
  canvas.
- The graph is a read-only view over `GET /api/v1/benchmark-graph`. That
  endpoint groups the existing dashboard comparison results; it does not fetch
  benchmarks, invent missing values or change any calculation.

### Real sample import

For the four sample CSVs in `C:\Users\ariji\Downloads`, the Upload page snapshot
status should show:

- **10 clients**, **27 folios** and **27 transactions**.
- **10 reconciliation warnings**, because each client’s summed folio AUM differs
  from the Portfolio Valuation current value.
- A warning that the Portfolio Valuation CSV had **no header row** and was read
  using the fixed 13-column layout.
- All benchmark comparisons remain **Not available** until mappings are reviewed
  and local benchmark levels are imported on the Benchmark Data screen.

Open the Graph to inspect individual folios. Each popup reports the same values
as before, including **₹5,000 invested**, **₹50,000 AUM**, **285 days** holding
period, **900.00% absolute return** and approximately **1,808.54% XIRR**.

## Upload the four real files

Export these four files from InvestWell: **Client Details**, **Folios**,
**Portfolio Valuation** and **Transaction Statement**. Use the same export run
for all four, and keep the exported file names so the app can check their dates.

Upload in this order:

1. In **Client Details**, choose the Client Details export.
2. In **Folios**, choose the Folios export.
3. In **Portfolio Valuation**, choose the Portfolio Valuation export.
4. In **Transaction Statement**, choose the Transaction Statement export.
5. Click **Preview import**.
6. While the preview runs, a progress panel names the current stage and shows
   elapsed seconds. The browser remains responsive because row parsing and
   matching run outside the request loop.
7. Review:
   - the detected sheet/header row or the headerless-CSV warning;
   - the valuation date from the Portfolio Valuation report;
   - the export-run check based on dates in the file names;
   - the columns used, other columns, and ignored sensitive columns;
   - rows read, imported, matched, skipped and why (blank, total, duplicate,
     missing required fields or other unreadable rows);
   - invalid dates and amounts, unmatched clients, unmatched transactions,
     unknown transaction types and one-legged switch warnings;
   - client matching and reconciliation warnings.
8. If there are no blocking errors, click **Confirm import and replace
   snapshot**. Nothing is saved until this step.

All four files must come from the same export run. The valuation date for the
batch is taken from the Portfolio Valuation report date and applied to every
folio in that import. XLSX and CSV are accepted for all four slots.

### File limits, large exports and progress

- Each file can be up to **25 MB**. The limit is checked in the browser and again
  while the API streams the upload to temporary local storage.
- Each file can have up to **100,000 data rows**. An XLSX may expand to at most
  **256 MB**; zip-bomb expansion is rejected before reading.
- The importer reads only the first 40 rows to find headers, then streams data
  rows. It keeps normalized records, not a copy of the workbook in memory.
- A compact preview is returned to the browser. The full normalized plan stays
  in `data/local/previews/` for confirmation, so the preview screen does not
  download thousands of raw-looking rows.
- The preview issue list is capped at **200 issues** in the browser and **500**
  in the stored plan, with a summary issue explaining the cap. All counts cover
  every row; only the list is capped.
- Temporary upload folders are deleted after each preview or benchmark import.

### Skipped and invalid rows

The preview separates these outcomes instead of silently changing data:

- **Blank rows**, **total/summary rows**, and exact **duplicate rows** are
  skipped and counted.
- Rows missing a required field, such as a folio number or scheme name, are
  skipped with the reason.
- An invalid transaction date or amount is retained for review but excluded
  from holding-period, return and XIRR calculations. The folio shows **Not
  available**, and the preview reports the invalid date/amount row.
- An unmatched client, folio or transaction is kept as **Unmatched — needs
  review**; it is never forced onto a client or guessed.
- If every folio and portfolio row is unmatched, the preview is blocked with a
  readable error. If all client keys fail to match, the confirmation is blocked.

### Human-readable errors

The API never returns a Python stack trace to the browser. Expected problems are
shown as short messages: missing files or headers, unsupported file types, an
empty/oversized file, a damaged XLSX, a missing Portfolio report date, a missing
mapping, invalid dates/amounts, duplicate/total/blank rows, unmatched
transactions, and benchmark date gaps. Unexpected failures show a generic
message while technical details remain in the local server log. The current
snapshot is not changed unless confirmation succeeds.

### Portfolio Valuation CSV fallback

If the Portfolio Valuation CSV has no recognizable header, the importer accepts
only the validated fixed 13-column layout:

1. client name
2. app code
3. IWELL code
4. PAN (ignored)
5. balance units
6. purchase value
7. current value
8. one-day change
9. dividend
10. average holding days
11. gain
12. absolute return
13. CAGR

A visible warning is shown in the preview. If the structure is not exactly this
layout, the import is blocked instead of guessing.

### Client matching

1. **IWELL CODE** is the main key. It is stored as text, trimmed, and a leading
   apostrophe is removed. It is never converted to a number, and `.0` forms are
   normalized.
2. **IWELL CODE 2** is tried if the main code is not found.
3. **APP CODE / APPCODE** is tried next.
4. **Client name** is used only as a last-resort fallback and only when exactly
   one client has that exact normalized name.
5. Anything still unmatched is shown as **Unmatched — needs review**. It is not
   forced onto a client. If every folio row and every portfolio row are
   unmatched, the preview is blocked with a message to check that the files are
   from the same export run.

PAN is not used as a database key or stored field.

## Calculation rules

- **Folio current value** comes from the Folios `AUM` column, exactly as
  reported.
- **Client current value** comes from the Portfolio Valuation `CURRENT VALUE`
  column, exactly as reported. It is never allocated across folios.
- **Gross invested** = gross purchases + SIP installments + switch-ins.
- **Net invested** = gross invested − redemptions − switch-outs.
- **Holding period** = earliest valid purchase/SIP/switch-in date to the
  Portfolio Valuation report date.
- **Absolute return** =
  `(current value + redemption proceeds + switch-out proceeds − gross invested)
  ÷ gross invested × 100`.
- **XIRR** uses dated cash flows: purchases/SIPs/switch-ins are negative;
  redemptions/switch-outs are positive; the folio current value on the
  valuation date is the final positive flow. XIRR is shown as a percentage.
- Metrics are calculated only from matched transaction rows. Missing dates,
  missing amounts, zero amounts and unknown transaction types are excluded and
  reported; they are never repaired or estimated.
- If the folio has no AUM, invested amount can still be shown, but absolute
  return and XIRR are **Not available**.
- If the transaction file is omitted through the API, folio return metrics are
  **Not available**. The browser requires all four slots for a normal import.
- A one-legged or ambiguous switch is flagged for review. The missing leg is
  never inferred.
- If the sum of a client’s folio AUM values differs from the client-level
  current value by more than ₹1, a reconciliation warning is shown. The total
  row in the Portfolio Valuation file is skipped as a client.
- Client-level **ABSOLUTE RETURN** and **CAGR** are displayed exactly as
  reported by InvestWell. They are not recalculated.
- Blank or malformed numbers are shown as **Not available** and recorded as an
  import issue.

## Benchmark comparison

Automatic keyword mappings are stored as `needs_review` and are **never** used
for comparison. A comparison requires both:

1. a mapping approved on the **Benchmark Data** screen (stored in SQLite as
   `reviewed`);
2. local closing levels in SQLite for every required date, including the
   Portfolio Valuation date, the first transaction date and every dated
   transaction cash flow.

The coverage panel checks these dates in advance. It reports schemes that still
need mapping or review, series with no local levels, whether the valuation date
and first transaction dates are covered, and the exact missing dates. A missing
level makes the comparison **Not available** or **Levels missing**; it is never
interpolated, copied from a nearby date, or estimated.

### Importing benchmark levels

The level importer accepts `.csv` and `.xlsx` files in either layout.

Long format:

```csv
benchmark_name,date,level
Nifty 50 TRI,2026-01-15,210.00
Nifty 50 TRI,2026-10-27,225.00
```

Wide format:

```csv
date,Nifty 50 TRI,Nifty Midcap 150 TRI
2026-01-15,210.00,250.00
2026-10-27,225.00,272.00
```

Dates may be ISO or the configured Indian formats. Levels must be positive.
Invalid rows are skipped and shown as warnings. Existing values for the same
benchmark/date are updated. Other benchmark series and earlier dates are kept.
Levels are never fetched from the internet and missing dates are never
interpolated.

### Comparison method

- **Single purchase, no SIP/switch/redemption:** compare the folio absolute
  return with the benchmark point-to-point return from the first purchase date
  to the valuation date.
- **SIP, multiple purchases, redemption or switch:** apply the same dated cash
  flows to the benchmark level series, calculate benchmark XIRR, and compare it
  with folio XIRR. Redemption and switch-out proceeds are dated positive flows;
  purchases, SIPs and switch-ins are dated negative flows.
- **Difference** = folio return/XIRR − benchmark return/XIRR. Positive is green
  (folio ahead); negative is red (folio behind).
- If the mapping is missing or unreviewed, a required level is missing, or a
  return cannot be solved, the comparison shows **Not available** with the
  reason, including **Levels missing** where appropriate.

The **Benchmark Data** screen manages mappings and local levels. The **Graph**
screen is a read-only clustered view of those results. It never changes a
mapping or a comparison and never downloads benchmark data.

## Column mapping

Column aliases are configuration-driven in
`config/investwell_columns.yaml`. Header matching ignores case, punctuation and
extra spaces, and the first configured alias wins when a file contains
lookalike columns such as `SCHEME NAME` and `FUND NAME`, or `FOLIO NO` and
`ACCOUNT NO`. The importer scans for the header row. If a required column is
missing, the preview is blocked with a clear message instead of zero-filling the
field.

## Data and reset

- SQLite database: `data/local/mfd.sqlite3`
- Preview JSON: `data/local/previews/`
- Temporary uploads: `data/local/uploads/` (deleted after each request)
- Original uploaded files are not kept as part of the snapshot.
- Confirming a new import replaces the current local snapshot. This keeps the
  dashboard consistent with one export run. Reviewed benchmark mappings are
  preserved by normalized scheme name, and imported benchmark levels are not
  deleted.
- To start from an empty database, stop the app and delete
  `data/local/mfd.sqlite3`; it is recreated on the next start. This also removes
  reviewed mappings and benchmark levels. Preview JSON files can be deleted
  from `data/local/previews/` when they are no longer needed.

## Tests and production build

Backend tests (Milestone 7 includes a 5,000-folio / 10,000-transaction import,
row-skip diagnostics, invalid dates/amounts, unmatched clients and transactions,
25 MB limit handling, partial benchmark coverage and 200+ node graph data):

```powershell
cd "C:\Users\ariji\Desktop\Shontu AI\mfd-dashboard"
.\.venv\Scripts\python.exe -m pytest -q apps/api
```

Frontend tests (200+ folio layout time/determinism and upload validation) and
production build:

```powershell
cd "C:\Users\ariji\Desktop\Shontu AI\mfd-dashboard\apps\web"
npm test
npm run build
```

## Project structure

```text
mfd-dashboard/
  apps/
    api/                 FastAPI + SQLAlchemy backend
      src/mfd_dashboard/
        ingest/          XLSX/CSV loader, column detection, preview/confirm
        db/              SQLite models and session
        api/             local API routes
        calculations.py  transaction classification, returns and XIRR
        dashboard.py     client summary, folio metrics, benchmark comparison
        benchmarks.py    benchmark categories and automatic suggestions
        benchmark_coverage.py exact required-date and missing-date diagnostics
        benchmark_data.py     local level parser and SQLite storage
        benchmark_graph.py    read-only graph clusters and node states
        benchmark_mappings.py local mapping review and updates
        demo.py          synthetic four-file demo generator
      tests/
    web/                 Next.js + Tailwind frontend
      src/app/graph/     /graph page shell
      src/components/    graph, inspector and shared folio detail popup
      src/lib/           API client, types, formatting and local graph layout
      tests/             Node tests for graph layout and upload validation
  config/                column aliases and benchmark categories
  data/local/            private database, previews and temporary uploads
  samples/investwell_demo/  synthetic demo files
  samples/benchmark_levels/ synthetic demo benchmark levels
  docs/                  milestone notes
```

## Troubleshooting

- **“Could not reach local API”**: start the backend terminal and confirm it is
  running at `http://127.0.0.1:8000/api/v1/health`.
- **“Required column … was not found”**: check that the correct file was
  selected, or add the real header alias to
  `config/investwell_columns.yaml`.
- **“File is larger than 25 MB”**: export a smaller date range or split the
  snapshot. The limit applies to each of the four files independently.
- **A large file takes time**: preview streams rows and keeps the browser
  responsive; the progress panel shows the current stage and elapsed time. Do
  not start a second import until the first finishes.
- **The preview row counts do not match the spreadsheet**: blank, total,
  duplicate and incomplete rows are intentionally skipped; the file summary
  lists each reason and count.
- **Portfolio CSV warning**: the headerless fallback only accepts the fixed
  13-column layout. Export the file with headers or use the exact layout.
- **“report date was not found”**: the Portfolio Valuation file must contain a
  line such as `Report printed on: 27-10-2026` above the table.
- **“Unmatched — needs review”**: the folio, transaction or portfolio row has no
  matching IWELL code, fallback code, or unique exact client name.
- **“Not available in this file”**: the Folios export had no AUM for that folio.
  The app does not estimate it.
- **“XIRR could not be calculated”**: the folio needs at least one negative and
  one positive dated cash flow, plus a folio AUM on the valuation date.
- **Benchmark comparison shows Not available**: open **Benchmark Data**, approve
  the scheme mapping, and import local levels covering every required
  transaction/valuation date. The coverage panel lists the exact missing dates.
- **Levels missing**: the imported series does not have a level for a specific
  required date. Add that date; the app does not interpolate. The folio popup
  shows the missing dates and the coverage panel shows the full list.
- **Yellow benchmark badge**: every automatic mapping starts as **Needs
  Review** by design. Approving or changing it saves a reviewed mapping in
  SQLite.
- **Every graph folio is amber**: review the scheme mappings and import local
  benchmark levels on **Benchmark Data**. The graph never treats an unreviewed
  mapping or an incomplete date series as a comparison.
- **Graph folio is grey / Not available**: the folio has no dated transactions,
  no folio AUM/current value, or a return that cannot be calculated. Open its
  popup for the exact reason. Grey is not a benchmark-date problem; missing
  benchmark dates show as amber **Needs review**.
- **A folio changed from amber to grey**: the mapping is now approved, but the
  comparison still cannot be calculated from the available transactions or
  values. The popup says which input is missing.
- **Graph shows an empty benchmark nucleus**: no folio is currently mapped to
  that benchmark. The nucleus stays visible by design; it is not an error.
- **Folio labels are hidden at very low zoom**: this is deliberate for large
  graphs. Hover a node for its full detail, or zoom in one step to reveal client
  names and then scheme names. Labels never overlap; some secondary scheme
  labels may wait until there is room.
- **Search dimmed the graph**: search deliberately dims non-matching nodes to
  make matches easy to find. Clear the search or click **Clear filters** to
  restore the full view; no nodes were removed.

## Switching to PostgreSQL later

The database layer uses SQLAlchemy. Set `MFD_DATABASE_URL` to a PostgreSQL URL
when needed; Milestone 3 intentionally has no PostgreSQL or Docker setup.
