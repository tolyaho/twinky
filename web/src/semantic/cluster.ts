// Stage D: grouping messages by meaning. Pure functions over unit vectors — no model, no I/O — so
// the evaluation harness and the browser worker run exactly the same code.
//
// The historical experiment used single-link agglomeration: two messages joined if ANY chain of
// pairs above the threshold connected them, so "A is like B, B is like C" put A and C together
// even when they meant different things (evals/grouping/README.md: precision 0.164 on varied chat).
// The default here is center-based: a message joins a group only if it is close to the group's
// center itself, never through an intermediary. Single and average linkage stay available so the
// evaluation can compare them on the same data.

export interface Item {
  /** the normalised text; identical messages are one item */
  key: string;
  vec: Float32Array;
  /** how many messages carry this text */
  weight: number;
  authors: ReadonlySet<string>;
}

export type Method = "single" | "average" | "center";

export interface ClusterOptions {
  method: Method;
  /** cosine similarity a message needs to its group's center (or, for linkage, between groups) */
  threshold: number;
  /** a group needs at least this many messages … */
  minMessages: number;
  /** … from at least this many distinct chatters */
  minAuthors: number;
  /**
   * Raise the threshold to this quantile of the window's own pairwise similarities when that is
   * higher. Chat where everything is short and colloquial looks uniformly similar to an embedding
   * model; a fixed threshold that works on varied chat then merges everything on uniform chat.
   */
  adaptiveQuantile?: number;
  /** center method: centroid refinement passes (0 = none) */
  refine?: number;
  /**
   * center method: afterwards, merge groups whose centers are themselves at least `threshold`
   * apart, so one topic found from two seeds becomes one group. Centers, not members, decide —
   * a merge never happens through a chain of messages.
   */
  mergeCenters?: boolean;
}

export const dot = (a: Float32Array, b: Float32Array): number => {
  let s = 0;
  for (let i = 0; i < a.length; i++) s += a[i] * b[i];
  return s;
};

function normalise(v: Float32Array): Float32Array {
  let n = 0;
  for (let i = 0; i < v.length; i++) n += v[i] * v[i];
  n = Math.sqrt(n) || 1;
  for (let i = 0; i < v.length; i++) v[i] /= n;
  return v;
}

/** Weighted mean direction of some items — the group's center. */
export function centroid(items: readonly Item[], members: readonly number[]): Float32Array {
  const c = new Float32Array(items[members[0]].vec.length);
  for (const m of members) {
    const v = items[m].vec;
    for (let i = 0; i < c.length; i++) c[i] += v[i] * items[m].weight;
  }
  return normalise(c);
}

function similarity(items: readonly Item[]): Float32Array {
  const n = items.length;
  const s = new Float32Array(n * n);
  for (let i = 0; i < n; i++) {
    s[i * n + i] = 1;
    for (let j = i + 1; j < n; j++) s[i * n + j] = s[j * n + i] = dot(items[i].vec, items[j].vec);
  }
  return s;
}

function effectiveThreshold(sim: Float32Array, n: number, o: ClusterOptions): number {
  if (!o.adaptiveQuantile || n < 8) return o.threshold;
  const vals: number[] = [];
  for (let i = 0; i < n; i++) for (let j = i + 1; j < n; j++) vals.push(sim[i * n + j]);
  vals.sort((a, b) => a - b);
  return Math.max(o.threshold, vals[Math.min(vals.length - 1, Math.floor(vals.length * o.adaptiveQuantile))]);
}

function single(sim: Float32Array, n: number, t: number): number[][] {
  const parent = Array.from({ length: n }, (_, i) => i);
  const find = (i: number): number => (parent[i] === i ? i : (parent[i] = find(parent[i])));
  for (let i = 0; i < n; i++)
    for (let j = i + 1; j < n; j++)
      if (sim[i * n + j] >= t) {
        const a = find(i), b = find(j);
        if (a !== b) parent[Math.max(a, b)] = Math.min(a, b);
      }
  const groups = new Map<number, number[]>();
  for (let i = 0; i < n; i++) (groups.get(find(i)) ?? groups.set(find(i), []).get(find(i))!).push(i);
  return [...groups.values()];
}

/** UPGMA: merge the two groups with the highest mean pairwise similarity while it is >= t. */
function average(sim: Float32Array, n: number, t: number): number[][] {
  const members: (number[] | null)[] = Array.from({ length: n }, (_, i) => [i]);
  const s = Float64Array.from(sim);
  for (;;) {
    let best = -Infinity, bi = -1, bj = -1;
    for (let i = 0; i < n; i++) {
      if (!members[i]) continue;
      for (let j = i + 1; j < n; j++) {
        if (!members[j]) continue;
        if (s[i * n + j] > best) (best = s[i * n + j]), (bi = i), (bj = j);
      }
    }
    if (bi < 0 || best < t) break;
    const a = members[bi]!, b = members[bj]!;
    for (let k = 0; k < n; k++) {
      if (!members[k] || k === bi || k === bj) continue;
      const v = (a.length * s[k * n + bi] + b.length * s[k * n + bj]) / (a.length + b.length);
      s[k * n + bi] = s[bi * n + k] = v;
    }
    members[bi] = [...a, ...b];
    members[bj] = null;
  }
  return members.filter((m): m is number[] => m !== null);
}

/**
 * Center-based: the item whose neighbourhood carries the most messages becomes a center, and its
 * group is the unassigned items close to IT. Then each group's centroid is recomputed and items
 * are reassigned to the nearest centroid they are close enough to, so a group is held together by
 * its center, never by a chain.
 */
function center(items: readonly Item[], sim: Float32Array, n: number, t: number, refine: number, merge = false): number[][] {
  const mass = new Float64Array(n);
  for (let i = 0; i < n; i++) for (let j = 0; j < n; j++) if (sim[i * n + j] >= t) mass[i] += items[j].weight;
  const order = Array.from({ length: n }, (_, i) => i).sort(
    (a, b) => mass[b] - mass[a] || (items[a].key < items[b].key ? -1 : 1),
  );
  const owner = new Int32Array(n).fill(-1);
  let groups: number[][] = [];
  for (const c of order) {
    if (owner[c] !== -1) continue;
    const g = [c];
    owner[c] = groups.length;
    for (let j = 0; j < n; j++) if (owner[j] === -1 && sim[c * n + j] >= t) (owner[j] = groups.length), g.push(j);
    groups.push(g);
  }
  for (let pass = 0; pass < refine; pass++) {
    const multi = groups.filter((g) => g.length > 1);
    const cents = multi.map((g) => centroid(items, g));
    const next: number[][] = multi.map(() => []);
    const loose: number[] = [];
    for (let i = 0; i < n; i++) {
      let best = -1, bs = t;
      for (let k = 0; k < cents.length; k++) {
        const v = dot(items[i].vec, cents[k]);
        if (v >= bs) (bs = v), (best = k);
      }
      if (best >= 0) next[best].push(i);
      else loose.push(i);
    }
    groups = [...next.filter((g) => g.length), ...loose.map((i) => [i])];
  }
  if (merge) {
    let multi = groups.filter((g) => g.length > 1);
    const single = groups.filter((g) => g.length === 1);
    for (;;) {
      const cents = multi.map((g) => centroid(items, g));
      let best = t, bi = -1, bj = -1;
      for (let i = 0; i < multi.length; i++)
        for (let j = i + 1; j < multi.length; j++) {
          const v = dot(cents[i], cents[j]);
          if (v >= best) (best = v), (bi = i), (bj = j);
        }
      if (bi < 0) break;
      multi = [...multi.filter((_, k) => k !== bi && k !== bj), [...multi[bi], ...multi[bj]]];
    }
    groups = [...multi, ...single];
  }
  return groups;
}

/** Groups of item indices that pass the size and chatter floors, biggest first. */
export function clusterItems(items: readonly Item[], o: ClusterOptions): number[][] {
  const n = items.length;
  if (n === 0) return [];
  const sim = similarity(items);
  const t = effectiveThreshold(sim, n, o);
  const raw =
    o.method === "single" ? single(sim, n, t) : o.method === "average" ? average(sim, n, t) : center(items, sim, n, t, o.refine ?? 2, o.mergeCenters);
  const keep = raw.filter((g) => {
    const messages = g.reduce((s, i) => s + items[i].weight, 0);
    const authors = new Set<string>();
    for (const i of g) for (const a of items[i].authors) authors.add(a);
    return messages >= o.minMessages && authors.size >= o.minAuthors;
  });
  const mass = (g: number[]) => g.reduce((s, i) => s + items[i].weight, 0);
  return keep.sort((a, b) => mass(b) - mass(a) || (items[a[0]].key < items[b[0]].key ? -1 : 1));
}

/** How tightly a group holds together: the mean similarity of its messages to its center. */
export function coherence(items: readonly Item[], g: readonly number[]): number {
  const c = centroid(items, g);
  let s = 0, w = 0;
  for (const i of g) (s += dot(items[i].vec, c) * items[i].weight), (w += items[i].weight);
  return w ? s / w : 0;
}
