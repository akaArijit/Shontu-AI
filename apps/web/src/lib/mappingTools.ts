export function toggleSchemeSelection(
  selected: ReadonlySet<number>,
  schemeId: number,
): Set<number> {
  const next = new Set(selected);
  if (next.has(schemeId)) next.delete(schemeId);
  else next.add(schemeId);
  return next;
}

export function setVisibleSchemeSelection(
  selected: ReadonlySet<number>,
  visibleIds: readonly number[],
  checked: boolean,
): Set<number> {
  const next = new Set(selected);
  for (const schemeId of visibleIds) {
    if (checked) next.add(schemeId);
    else next.delete(schemeId);
  }
  return next;
}

export interface SuggestionCandidate {
  scheme_id: number;
  review_status: string;
  suggested_benchmark?: string | null;
}

export function suggestionAcceptTargets(
  selected: ReadonlySet<number>,
  items: ReadonlyArray<SuggestionCandidate>,
): number[] {
  const pool =
    selected.size > 0
      ? items.filter((item) => selected.has(item.scheme_id))
      : items;
  return pool
    .filter(
      (item) =>
        item.review_status !== "reviewed" && Boolean(item.suggested_benchmark),
    )
    .map((item) => item.scheme_id);
}

export interface MappingStatusCounts {
  total_schemes: number;
  mapped_schemes: number;
  reviewed_schemes: number;
  needs_review_schemes: number;
  unmapped_schemes: number;
  total_folios: number;
  mapped_folios: number;
  needs_review_folios: number;
  unmapped_folios: number;
  suggested_schemes: number;
  suggested_folios: number;
}

export interface MappingSummaryCounts {
  schemes: number;
  reviewed: number;
  needs_review: number;
  unmapped: number;
}

export function summarizeMappings(
  items: ReadonlyArray<{
    review_status: string;
    folio_count: number;
    suggested_benchmark?: string | null;
  }>,
): {
  summary: MappingSummaryCounts;
  status_summary: MappingStatusCounts;
} {
  const reviewed = items.filter(
    (item) => item.review_status === "reviewed",
  ).length;
  const needsReview = items.filter(
    (item) => item.review_status === "needs_review",
  ).length;
  const unmapped = items.filter(
    (item) => item.review_status === "needs_mapping",
  ).length;
  const totalFolios = items.reduce((total, item) => total + item.folio_count, 0);
  const unmappedFolios = items
    .filter((item) => item.review_status === "needs_mapping")
    .reduce((total, item) => total + item.folio_count, 0);
  const needsReviewFolios = items
    .filter((item) => item.review_status === "needs_review")
    .reduce((total, item) => total + item.folio_count, 0);
  const suggested = items.filter(
    (item) =>
      item.suggested_benchmark && item.review_status !== "reviewed",
  );

  return {
    summary: {
      schemes: items.length,
      reviewed,
      needs_review: needsReview,
      unmapped,
    },
    status_summary: {
      total_schemes: items.length,
      mapped_schemes: reviewed + needsReview,
      reviewed_schemes: reviewed,
      needs_review_schemes: needsReview,
      unmapped_schemes: unmapped,
      total_folios: totalFolios,
      mapped_folios: totalFolios - unmappedFolios,
      needs_review_folios: needsReviewFolios,
      unmapped_folios: unmappedFolios,
      suggested_schemes: suggested.length,
      suggested_folios: suggested.reduce(
        (total, item) => total + item.folio_count,
        0,
      ),
    },
  };
}

export function keywordPreviewLabel(preview: {
  matched_scheme_count: number;
  matched_folio_count: number;
  matched_unmapped_folio_count: number;
}): string {
  const schemes = preview.matched_scheme_count.toLocaleString("en-IN");
  const folios = preview.matched_folio_count.toLocaleString("en-IN");
  const unmapped = preview.matched_unmapped_folio_count.toLocaleString("en-IN");
  return (
    `${schemes} scheme${preview.matched_scheme_count === 1 ? "" : "s"} and ` +
    `${folios} folio${preview.matched_folio_count === 1 ? "" : "s"} match. ` +
    `${unmapped} folio${preview.matched_unmapped_folio_count === 1 ? "" : "s"} ` +
    "would move out of Other / Unmapped."
  );
}

export function mappingImportLabel(preview: {
  summary: {
    schemes_to_update: number;
    folios_affected: number;
    unmapped_folios_affected: number;
  };
}): string {
  return (
    `${preview.summary.schemes_to_update.toLocaleString("en-IN")} scheme(s) and ` +
    `${preview.summary.folios_affected.toLocaleString("en-IN")} folio(s) will be updated. ` +
    `${preview.summary.unmapped_folios_affected.toLocaleString("en-IN")} folio(s) ` +
    "will move out of Other / Unmapped."
  );
}
