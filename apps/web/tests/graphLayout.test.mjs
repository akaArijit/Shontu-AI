import assert from "node:assert/strict";
import { performance } from "node:perf_hooks";
import test from "node:test";

import { buildGraphLayout } from "../src/lib/graphLayout.ts";

const PERFORMANCES = [
  "ahead",
  "behind",
  "not_available",
  "needs_review",
];

function clusterInputs(folioCount, clusterCount = 7) {
  return Array.from({ length: clusterCount }, (_, clusterIndex) => ({
    id: `cluster-${clusterIndex}`,
    name: `Benchmark Cluster ${clusterIndex + 1}`,
    folios: Array.from({ length: folioCount }, (_, index) => ({
      id: `folio-${clusterIndex}-${index}`,
      performance:
        PERFORMANCES[(clusterIndex + index) % PERFORMANCES.length],
    })),
  }));
}

test("layout places more than 200 folios quickly and deterministically", () => {
  const inputs = clusterInputs(36);

  const started = performance.now();
  const layout = buildGraphLayout(inputs);
  const elapsed = performance.now() - started;

  assert.equal(layout.clusters.length, 7);
  assert.equal(layout.folios.length, 252);
  assert.equal(layout.folioRadius, 5.9);
  assert.ok(elapsed < 500, `layout took ${elapsed.toFixed(1)}ms`);
  assert.ok(
    Number.isFinite(layout.bounds.width) && layout.bounds.width > 0,
    "layout must have usable bounds",
  );
  assert.ok(
    layout.folios.every(
      (folio) => Number.isFinite(folio.x) && Number.isFinite(folio.y),
    ),
    "every folio needs finite coordinates",
  );

  const positions = new Set(
    layout.folios.map((folio) => `${folio.x.toFixed(3)}:${folio.y.toFixed(3)}`),
  );
  assert.equal(positions.size, layout.folios.length);

  const again = buildGraphLayout(inputs);
  assert.deepEqual(again, layout);
});

test("layout keeps every cluster and label inside positive bounds", () => {
  const layout = buildGraphLayout(clusterInputs(8, 3));

  for (const cluster of layout.clusters) {
    assert.ok(
      cluster.x - cluster.separationRadius >= layout.bounds.minX,
      `${cluster.name} extends left of the layout bounds`,
    );
    assert.ok(
      cluster.x + cluster.separationRadius <= layout.bounds.maxX,
      `${cluster.name} extends right of the layout bounds`,
    );
    assert.ok(
      cluster.y - cluster.outerRadius >= layout.bounds.minY,
      `${cluster.name} extends above the layout bounds`,
    );
    assert.ok(
      cluster.y + cluster.labelY + cluster.labelHeight <= layout.bounds.maxY,
      `${cluster.name} label extends below the layout bounds`,
    );
  }
});
