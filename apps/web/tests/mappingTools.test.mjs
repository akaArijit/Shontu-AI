import assert from "node:assert/strict";
import test from "node:test";

import {
  keywordPreviewLabel,
  mappingImportLabel,
  setVisibleSchemeSelection,
  suggestionAcceptTargets,
  summarizeMappings,
  toggleSchemeSelection,
} from "../src/lib/mappingTools.ts";

test("scheme selection toggles and can select or clear every filtered row", () => {
  let selected = new Set();
  selected = toggleSchemeSelection(selected, 4);
  selected = toggleSchemeSelection(selected, 9);
  assert.deepEqual([...selected].sort((a, b) => a - b), [4, 9]);

  selected = toggleSchemeSelection(selected, 4);
  assert.deepEqual([...selected], [9]);

  selected = setVisibleSchemeSelection(selected, [1, 2, 9], true);
  assert.deepEqual([...selected].sort((a, b) => a - b), [1, 2, 9]);

  selected = setVisibleSchemeSelection(selected, [1, 2], false);
  assert.deepEqual([...selected], [9]);
});

test("status totals count folios affected by unmapped schemes", () => {
  const before = summarizeMappings([
    { review_status: "reviewed", folio_count: 40, suggested_benchmark: null },
    { review_status: "needs_review", folio_count: 10, suggested_benchmark: "Nifty 50 TRI" },
    { review_status: "needs_mapping", folio_count: 15, suggested_benchmark: null },
  ]);
  assert.deepEqual(before.summary, {
    schemes: 3,
    reviewed: 1,
    needs_review: 1,
    unmapped: 1,
  });
  assert.equal(before.status_summary.total_folios, 65);
  assert.equal(before.status_summary.unmapped_folios, 15);
  assert.equal(before.status_summary.suggested_schemes, 1);
  assert.equal(before.status_summary.suggested_folios, 10);

  const after = summarizeMappings([
    { review_status: "reviewed", folio_count: 40, suggested_benchmark: null },
    { review_status: "reviewed", folio_count: 10, suggested_benchmark: null },
    { review_status: "reviewed", folio_count: 15, suggested_benchmark: null },
  ]);
  assert.equal(after.status_summary.mapped_schemes, 3);
  assert.equal(after.status_summary.unmapped_schemes, 0);
  assert.equal(after.status_summary.unmapped_folios, 0);
  assert.equal(before.status_summary.unmapped_folios - after.status_summary.unmapped_folios, 15);
});

test("accept suggestions targets only visible suggestions or the selected schemes", () => {
  const rows = [
    { scheme_id: 1, review_status: "needs_review", suggested_benchmark: "Nifty 50 TRI" },
    { scheme_id: 2, review_status: "needs_review", suggested_benchmark: null },
    { scheme_id: 3, review_status: "needs_mapping", suggested_benchmark: "Nifty IT TRI" },
    { scheme_id: 4, review_status: "reviewed", suggested_benchmark: "Nifty Bank TRI" },
  ];

  assert.deepEqual(suggestionAcceptTargets(new Set(), rows), [1, 3]);
  assert.deepEqual(suggestionAcceptTargets(new Set([3, 4]), rows), [3]);
  assert.deepEqual(suggestionAcceptTargets(new Set([2, 4]), rows), []);
  assert.deepEqual(
    suggestionAcceptTargets(new Set(), [
      { scheme_id: 9, review_status: "needs_review", suggested_benchmark: null },
    ]),
    [],
  );
});

test("keyword preview text states scheme, folio and unmapped impact before apply", () => {
  const label = keywordPreviewLabel({
    matched_scheme_count: 3,
    matched_folio_count: 12,
    matched_unmapped_folio_count: 7,
  });
  assert.match(label, /3 schemes and 12 folios match/);
  assert.match(label, /7 folios would move out of Other \/ Unmapped/);
});

test("mapping import text states validated impact before saving", () => {
  const label = mappingImportLabel({
    summary: {
      schemes_to_update: 4,
      folios_affected: 80,
      unmapped_folios_affected: 65,
    },
  });
  assert.match(label, /4 scheme\(s\) and 80 folio\(s\) will be updated/);
  assert.match(label, /65 folio\(s\) will move out of Other \/ Unmapped/);
});
