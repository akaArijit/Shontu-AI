import type { GraphPerformance } from "@/lib/types";

export interface GraphLayoutClusterInput {
  id: string;
  name: string;
  folios: Array<{ id: string; performance: GraphPerformance }>;
}

export interface PositionedCluster {
  id: string;
  name: string;
  x: number;
  y: number;
  nucleusRadius: number;
  outerRadius: number;
  clusterRadius: number;
  separationRadius: number;
  labelY: number;
  labelHeight: number;
  labelLines: string[];
}

export interface PositionedFolio {
  id: string;
  clusterId: string;
  x: number;
  y: number;
  index: number;
  performance: GraphPerformance;
}

export interface GraphBounds {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
  width: number;
  height: number;
  centerX: number;
  centerY: number;
}

export interface GraphLayout {
  clusters: PositionedCluster[];
  folios: PositionedFolio[];
  bounds: GraphBounds;
  folioRadius: number;
}

const TWO_PI = Math.PI * 2;
const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5));

function hashUnit(value: string): number {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0) / 4294967295;
}

function wrapName(name: string, maxChars = 22): string[] {
  const words = name.split(/\s+/).filter(Boolean);
  const lines: string[] = [];
  let current = "";
  for (const word of words) {
    const candidate = current ? `${current} ${word}` : word;
    if (candidate.length <= maxChars || !current) {
      current = candidate;
    } else {
      lines.push(current);
      current = word;
    }
    if (lines.length === 2) break;
  }
  if (current) lines.push(current);
  return lines.length > 0 ? lines : [name];
}

function makeBounds(clusters: PositionedCluster[], padding = 34): GraphBounds {
  if (clusters.length === 0) {
    return {
      minX: -100,
      maxX: 100,
      minY: -100,
      maxY: 100,
      width: 200,
      height: 200,
      centerX: 0,
      centerY: 0,
    };
  }
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

interface Ring {
  radius: number;
  take: number;
  offset: number;
}

interface SizedCluster extends GraphLayoutClusterInput {
  count: number;
  rings: Ring[];
  nucleusRadius: number;
  outerRadius: number;
  maxOffset: number;
  labelLines: string[];
  labelY: number;
  labelHeight: number;
  clusterRadius: number;
  separationRadius: number;
}

interface Point {
  x: number;
  y: number;
}

function initialClusterPositions(clusters: SizedCluster[]): Point[] {
  if (clusters.length === 0) return [];
  if (clusters.length === 1) return [{ x: 0, y: 0 }];

  const maxRadius = Math.max(...clusters.map((item) => item.separationRadius));
  const spread = Math.max(
    maxRadius * 1.55,
    Math.sqrt(clusters.length) * maxRadius * 0.82,
  );

  return clusters.map((cluster, index) => {
    const angle =
      index * GOLDEN_ANGLE + (hashUnit(cluster.id) - 0.5) * 0.34;
    const radialJitter = 0.91 + hashUnit(cluster.name) * 0.18;
    const radius =
      spread * Math.sqrt((index + 0.7) / clusters.length) * radialJitter;
    return {
      x: Math.cos(angle) * radius,
      y: Math.sin(angle) * radius,
    };
  });
}

/**
 * Deterministic force relaxation for the benchmark nuclei.
 *
 * The golden-angle seed gives every data set an organic starting shape. Pairwise
 * collision forces then separate nuclei using their own outer radius and label
 * width, while a very light centre pull keeps the map compact. There is no
 * randomness at runtime, so the same snapshot always produces the same layout.
 */
function relaxClusterPositions(
  points: Point[],
  clusters: SizedCluster[],
): Point[] {
  if (points.length <= 1) return points.map((point) => ({ ...point }));

  const current = points.map((point) => ({ ...point }));
  const gap = 58;
  const iterations = points.length > 18 ? 260 : 220;

  for (let iteration = 0; iteration < iterations; iteration += 1) {
    const forces = current.map(() => ({ x: 0, y: 0 }));

    for (let left = 0; left < current.length; left += 1) {
      for (let right = left + 1; right < current.length; right += 1) {
        const dx = current[right].x - current[left].x;
        const dy = current[right].y - current[left].y;
        const distance = Math.max(0.001, Math.hypot(dx, dy));
        const nx = dx / distance;
        const ny = dy / distance;
        const minimum =
          clusters[left].separationRadius +
          clusters[right].separationRadius +
          gap;

        if (distance < minimum) {
          const push = (minimum - distance) * 0.54;
          forces[left].x -= nx * push;
          forces[left].y -= ny * push;
          forces[right].x += nx * push;
          forces[right].y += ny * push;
        } else {
          const longRange = Math.min(
            1.8,
            ((minimum * minimum) / (distance * distance)) * 0.22,
          );
          forces[left].x -= nx * longRange;
          forces[left].y -= ny * longRange;
          forces[right].x += nx * longRange;
          forces[right].y += ny * longRange;
        }
      }
    }

    for (let index = 0; index < current.length; index += 1) {
      const distance = Math.max(1, Math.hypot(current[index].x, current[index].y));
      const pull = distance * 0.0012;
      forces[index].x -= (current[index].x / distance) * pull;
      forces[index].y -= (current[index].y / distance) * pull;

      current[index].x += forces[index].x * 0.68;
      current[index].y += forces[index].y * 0.68;
    }
  }

  // A final direct separation pass guarantees that label cards never collide,
  // even when the relaxation stops just short of the required distance.
  for (let pass = 0; pass < 80; pass += 1) {
    let changed = false;
    for (let left = 0; left < current.length; left += 1) {
      for (let right = left + 1; right < current.length; right += 1) {
        const dx = current[right].x - current[left].x;
        const dy = current[right].y - current[left].y;
        const distance = Math.max(0.001, Math.hypot(dx, dy));
        const minimum =
          clusters[left].separationRadius +
          clusters[right].separationRadius +
          gap;
        if (distance >= minimum) continue;
        const push = (minimum - distance) / 2 + 0.5;
        const nx = dx / distance;
        const ny = dy / distance;
        current[left].x -= nx * push;
        current[left].y -= ny * push;
        current[right].x += nx * push;
        current[right].y += ny * push;
        changed = true;
      }
    }
    if (!changed) break;
  }

  const centerX =
    current.reduce((total, point) => total + point.x, 0) / current.length;
  const centerY =
    current.reduce((total, point) => total + point.y, 0) / current.length;
  return current.map((point) => ({
    x: point.x - centerX,
    y: point.y - centerY,
  }));
}

/**
 * Build a deterministic, organic clustered layout once per data set.
 *
 * Benchmark nuclei use a seeded force-directed placement. Folios remain in
 * evenly spaced concentric rings around their own nucleus, so filtering never
 * moves the graph and 200+ folios stay readable. Labels and ring spacing are
 * measured before relaxation so clusters and label cards do not collide.
 */
export function buildGraphLayout(
  clusterInputs: GraphLayoutClusterInput[],
): GraphLayout {
  const sized: SizedCluster[] = clusterInputs.map(
    (cluster, clusterIndex) => {
      const count = cluster.folios.length;
      const nucleusRadius = count
        ? Math.min(42, 28 + Math.sqrt(count) * 2.2)
        : 27;
      const spacing =
        count > 150 ? 26 : count > 80 ? 30 : count > 30 ? 34 : 40;
      const rings: Ring[] = [];
      let maxOffset = nucleusRadius;
      if (count > 0) {
        let remaining = count;
        let radius = nucleusRadius + 30;
        let ringIndex = 0;
        while (remaining > 0) {
          const capacity = Math.max(
            1,
            Math.floor((TWO_PI * radius) / spacing),
          );
          const take = Math.min(capacity, remaining);
          rings.push({
            radius,
            take,
            offset:
              hashUnit(cluster.id) * TWO_PI +
              ringIndex * 0.79 +
              clusterIndex * 0.31,
          });
          remaining -= take;
          maxOffset = radius;
          radius += spacing;
          ringIndex += 1;
        }
      }
      const labelLines = wrapName(cluster.name, 24);
      const labelY = maxOffset + (count > 0 ? 14 : 12);
      const labelHeight = labelLines.length * 13 + 45;
      const clusterRadius = labelY + labelHeight + 12;
      const labelWidth = Math.max(
        160,
        ...labelLines.map((line) => line.length * 7 + 28),
      );
      return {
        ...cluster,
        count,
        rings,
        nucleusRadius,
        outerRadius: Math.max(nucleusRadius, maxOffset),
        maxOffset,
        labelLines,
        labelY,
        labelHeight,
        clusterRadius,
        separationRadius: Math.max(
          clusterRadius * 0.84,
          maxOffset + 36,
          labelWidth / 2 + 18,
        ),
      };
    },
  );

  const positions = relaxClusterPositions(
    initialClusterPositions(sized),
    sized,
  );

  const positionedClusters: PositionedCluster[] = sized.map(
    (cluster, index) => ({
      id: cluster.id,
      name: cluster.name,
      x: positions[index]?.x ?? 0,
      y: positions[index]?.y ?? 0,
      nucleusRadius: cluster.nucleusRadius,
      outerRadius: cluster.outerRadius,
      clusterRadius: cluster.clusterRadius,
      separationRadius: cluster.separationRadius,
      labelY: cluster.labelY,
      labelHeight: cluster.labelHeight,
      labelLines: cluster.labelLines,
    }),
  );

  const positionedFolios: PositionedFolio[] = [];
  sized.forEach((cluster, clusterIndex) => {
    const center = positionedClusters[clusterIndex];
    let index = 0;
    for (const ring of cluster.rings) {
      for (let position = 0; position < ring.take; position += 1) {
        const angle =
          ring.offset + (position * TWO_PI) / Math.max(1, ring.take);
        positionedFolios.push({
          id: cluster.folios[index].id,
          clusterId: cluster.id,
          x: center.x + Math.cos(angle) * ring.radius,
          y: center.y + Math.sin(angle) * ring.radius,
          index,
          performance: cluster.folios[index].performance,
        });
        index += 1;
      }
    }
  });

  return {
    clusters: positionedClusters,
    folios: positionedFolios,
    bounds: makeBounds(positionedClusters),
    folioRadius: positionedFolios.length > 160 ? 5.9 : 6.8,
  };
}
