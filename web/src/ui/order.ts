// Visual stability for the board. Groups are recounted every ~1.5s, and two groups with nearly
// the same count trade places on every recount if they are simply sorted — the board flickers and
// a reader loses track of the row they were watching. Rows therefore keep their previous order
// unless one *clearly* overtakes the row above it. New groups enter at their true rank. The
// counts themselves are never touched; only the order is damped, and only within the margin.

/** How far a row must lead the row above it to take its place. */
export function overtakeMargin(count: number): number {
  return Math.max(2, Math.ceil(count * 0.1));
}

export function stableOrder<T extends { key: string; count: number }>(
  groups: readonly T[],
  previous: readonly string[],
): T[] {
  const byKey = new Map(groups.map((g) => [g.key, g]));
  const order: T[] = [];
  for (const k of previous) {
    const g = byKey.get(k);
    if (g) order.push(g);
  }
  const placed = new Set(order.map((g) => g.key));
  for (const g of groups) {
    if (placed.has(g.key)) continue;
    const at = order.findIndex((o) => o.count < g.count);
    if (at === -1) order.push(g);
    else order.splice(at, 0, g);
  }
  // Bubble rows up past any row they now clearly lead. Bounded: n is at most a few dozen.
  for (let pass = 0; pass < order.length; pass++) {
    let moved = false;
    for (let i = 1; i < order.length; i++) {
      const above = order[i - 1];
      const below = order[i];
      if (below.count - above.count >= overtakeMargin(above.count)) {
        order[i - 1] = below;
        order[i] = above;
        moved = true;
      }
    }
    if (!moved) break;
  }
  return order;
}
