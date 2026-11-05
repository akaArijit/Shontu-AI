# Milestone 2 notes

> Historical record. The YAML-based benchmark review/level configuration
> described below was replaced in Milestone 3 by the local SQLite mapping screen
> and benchmark-level importer. See `docs/MILESTONE_3_NOTES.md`.

## Approved scope

Milestone 2 adds the Transaction Statement as the fourth InvestWell import and
uses it to calculate folio-level returns. The Client Details, Folios and
Portfolio Valuation files from Milestone 1 remain the source for identities,
folio values and client-level reported values.

XLSX and CSV are accepted for all four slots. The Portfolio Valuation CSV also
accepts the validated fixed 13-column layout when no header row is present; a
visible warning is shown and an inexact layout is blocked.

## Calculation rules

- **Gross invested** = gross purchases + SIP installments + switch-ins.
- **Net invested** = gross invested − redemptions − switch-outs.
- **Holding period** = earliest valid purchase/SIP/switch-in date to the
  Portfolio Valuation report date.
- **Absolute return** =
  `(current value + redemption proceeds + switch-out proceeds − gross invested)
  ÷ gross invested × 100`.
- **XIRR** uses dated cash flows: purchase/SIP/switch-in outflows are negative;
  redemption/switch-out inflows are positive; the folio AUM on the valuation
  date is the final positive flow.
- Folios `AUM` is the folio current value. Portfolio `CURRENT VALUE` is used only
  for client-level totals and is never allocated across folios.
- Missing dates, missing amounts, zero amounts and unknown transaction types are
  excluded from the calculations and reported as issues. They are not repaired.
- A folio with transaction dates but no AUM can show gross invested, while
  absolute return and XIRR stay **Not available**.
- One-legged or ambiguous switch legs are flagged for review. The missing leg
  is not inferred.

## Benchmark comparison

Every automatic keyword mapping remains **Needs Review**. Comparisons are
available only when:

1. `config/benchmark_reviews.yaml` has an exact reviewed scheme name and
   benchmark name; and
2. `config/benchmark_levels.yaml` has a local closing level for every
   transaction date and the valuation date.

For SIP or multiple-flow folios, the same dated cash flows are simulated on the
benchmark. Missing levels are not interpolated. In all other cases the UI shows
**Not available** with the exact reason.

There is no benchmark-editing screen, benchmark graph, web search or automatic
benchmark download.

## Matching and switch pairing

Transactions use the same client identity order as the other files: IWELL CODE,
IWELL CODE 2, APPCODE, then a unique exact normalized client name. A transaction
is matched to a Folios row by normalized folio number and normalized scheme
name. A missing folio, scheme mismatch or client mismatch is kept for review.

Switch legs are paired only when one out-leg and one in-leg share the same
client, date and rounded absolute amount. Multiple legs with the same key are
marked ambiguous. Legs missing a folio, date or amount are marked as unable to
pair. The importer never creates the missing leg.

## Validation performed

- Backend suite covers purchase-only, multiple SIPs, redemption,
  switch-out/switch-in pairing, missing dates, missing amounts, unknown types,
  missing transaction folio, scheme mismatch, missing folio AUM, missing client
  current value, folio-AUM/client-value mismatch, missing reviewed mapping,
  missing benchmark levels, the headerless Portfolio CSV fallback and alias
  precedence.
- The four sample CSVs in `C:\Users\ariji\Downloads` preview and confirm with 10
  clients, 27 folios, 10 portfolio rows and 27 matched transactions. Every folio
  yields ₹5,000 gross invested, ₹50,000 folio AUM, 285 days, 900.00% absolute
  return and approximately 1,808.54% XIRR. All 10 clients show the expected
  folio-AUM/current-value reconciliation warning.
- The frontend production build and the backend test suite pass.

## Known limitations

- Benchmark comparisons remain unavailable until local levels and reviewed
  mappings are supplied.
- The sample export contains one transaction per folio, so multi-flow behavior
  is covered by synthetic tests rather than the sample file.
- The app still shows no graph, no NAV history and no transaction ledger.
- A transaction-file match can be reported as an info issue when the
  transaction’s client code/name is not present in Client Details but the folio
  itself matched. The folio match is used and no client is guessed.
