# Milestone 1 notes

## Approved three-file scope

The importer reads the three InvestWell XLSX exports directly:

1. **Client Details** — client master and matching keys.
2. **Folios** — folio, scheme, units and folio-level AUM.
3. **Portfolio Valuation** — client-level current value, gains, returns and
   report date.

There is no transaction ledger in this milestone.

## Key decisions

- **IWELL CODE** is the main matching key, stored as text. Leading apostrophes
  and surrounding spaces are trimmed; the value is never converted to a
  number.
- **IWELL CODE 2** and **APP CODE / APPCODE** are fallbacks.
- **Client name** is the last-resort fallback, and only when exactly one client
  has that exact normalized name.
- Unmatched rows are kept for review and labelled **Unmatched — needs review**.
- PAN is not a database key or a stored field. PAN, Aadhaar, contact, address,
  bank, KYC and nominee columns are ignored and reported in the preview.
- Portfolio Valuation `CURRENT VALUE` is the client-level current value.
- Folios `AUM` is the folio-level current value as reported.
- Client-level current value is never allocated across folios.
- A reconciliation warning appears when the sum of a client’s folio AUM values
  differs from the client-level current value by more than ₹1.
- Dashboard summary totals show **matched clients only**. Unmatched folio AUM
  and unmatched client current value are listed separately and are never added
  to the client summary.
- The Portfolio Valuation report date is the valuation date for the whole
  import batch. The total row is skipped as a client and used only for a
  total-row reconciliation check.
- Client-level `ABSOLUTE RETURN` and `CAGR` are shown exactly as reported by
  InvestWell.
- Folio invested amount, absolute return and holding period are **Not
  available** because these three files do not contain purchase value or folio
  purchase dates. They are not estimated.
- Rows without both a folio number and a scheme name are skipped and recorded.
- Malformed numbers are left blank as **Not available** and recorded as import
  issues.
- Every automatic benchmark mapping is stored in `scheme_benchmarks` with
  status `needs_review`.
- Confirming a preview replaces the previous local snapshot.

## Current limitations

- No folio-level purchase value, transaction dates or folio valuation date are
  present in the three files. Same-period benchmark comparison is therefore
  not attempted.
- The attached sample exports were partial/redacted, so overlapping client keys
  across the three files could not be empirically validated. The matcher is
  covered by synthetic XLSX tests.
- Benchmark categories are sample mappings, not live benchmarks.
- The benchmark editing screen is deferred.

## Deferred to Milestone 2

- Benchmark mapping edit/confirm workflow.
- Folio-level invested amount, return and holding period when a transaction or
  folio valuation export is available.
- Redemption/switch handling rules.
- Possibly XIRR and graph view (only after explicit approval).
- Better benchmark data source if required.
- Data cleanup/export and backup workflow.
