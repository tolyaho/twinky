// The audience timeline's numbers: how many of the window's messages were sent in each slice of
// time, in all and for the board's leading groups. Pure arithmetic over one recount.
//
// What a line means, exactly: the messages that are in a group at this recount, counted by when
// they were sent. Membership is the board's grouping now, applied to messages already in the
// window — nothing tracked the group before the board formed it, so a line that starts 40 s back
// says "these messages were sent then", not "this topic was noticed then".
//
// Slices are aligned to the clock, not to the window's edge, so a slice already drawn keeps its
// count from one recount to the next instead of shifting with every tick. The oldest slice is
// drawn only once it lies wholly inside the window and wholly after listening began (anything
// earlier is unknown, never zero); the newest one is still filling and is marked as such.
import type { ChatEvent } from "../cluster/types";

/** Groups drawn as lines: the board's leading few, plus the open one if it is not among them. */
export const SERIES_MAX = 3;
/** Colour slots; a group keeps its slot for as long as it stays on the chart. */
export const SLOTS = 4;

/**
 * Slice width per window: 10–15 points across the window. Finer than that, a group of a dozen
 * messages is mostly empty slices; coarser, a burst and a steady stream look the same.
 * web/eval/timeline-resolution.ts checks these on real chat (evals/timeline/resolution.json).
 */
export function bucketFor(windowMs: number): number {
  if (windowMs <= 30_000) return 3_000;
  if (windowMs <= 60_000) return 5_000;
  return 20_000;
}

export interface TimelineSeries {
  key: string;
  counts: number[];
}

export interface Timeline {
  bucketMs: number;
  /** the window drawn: [start, end] in event time */
  from: number;
  to: number;
  /** start of each drawn slice */
  starts: number[];
  /** all messages per slice */
  total: number[];
  /** the last slice is still filling */
  open: boolean;
  series: TimelineSeries[];
}

export interface TimelineInput {
  events: ReadonlyMap<string, ChatEvent>;
  windowStart: number;
  windowEnd: number;
  /** how much of the window this session listened to (`TickSnapshot.observedMs`) */
  observedMs: number;
  groups: readonly { key: string; event_ids: readonly string[] }[];
  bucketMs: number;
}

export function buildTimeline({ events, windowStart, windowEnd, observedMs, groups, bucketMs: b }: TimelineInput): Timeline {
  const since = windowEnd - observedMs; // listening began here
  const first = Math.ceil(Math.max(windowStart, since) / b) * b;
  let last = Math.floor(windowEnd / b) * b;
  let open = true;
  if (last === windowEnd) {
    // the slice starting exactly now has had no time to fill: the one before it is complete
    last -= b;
    open = false;
  }
  const n = last >= first ? (last - first) / b + 1 : 0;
  const starts = Array.from({ length: n }, (_, i) => first + i * b);
  const slot = (ts: number) => {
    if (ts < first || ts >= first + n * b) return -1;
    return Math.floor((ts - first) / b);
  };

  const total = new Array<number>(n).fill(0);
  for (const e of events.values()) {
    const i = slot(e.ts_ms);
    if (i >= 0) total[i]++;
  }
  const series = groups.map((g) => {
    const counts = new Array<number>(n).fill(0);
    for (const id of g.event_ids) {
      const e = events.get(id);
      const i = e ? slot(e.ts_ms) : -1;
      if (i >= 0) counts[i]++;
    }
    return { key: g.key, counts };
  });
  return { bucketMs: b, from: windowStart, to: windowEnd, starts, total, open: open && n > 0, series };
}

/** The groups drawn: the board's first few in its order, and the open group if it is further down. */
export function pickSeries<T extends { key: string }>(groups: readonly T[], selectedKey: string | null): T[] {
  const top = groups.slice(0, SERIES_MAX);
  if (selectedKey && !top.some((g) => g.key === selectedKey)) {
    const sel = groups.find((g) => g.key === selectedKey);
    if (sel) top.push(sel);
  }
  return top;
}

/**
 * Colour slots that follow the group, not its rank: a group keeps its slot while it is drawn, and
 * gets the same one back if it returns while that slot is still free. New groups take the lowest
 * free slot. `memory` is carried from one recount to the next (and dropped on a channel switch).
 */
export function assignSlots(keys: readonly string[], memory: Map<string, number>): Map<string, number> {
  const out = new Map<string, number>();
  const used = new Set<number>();
  // groups that already hold a slot keep it
  for (const k of keys) {
    const s = memory.get(k);
    if (s !== undefined && !used.has(s)) {
      out.set(k, s);
      used.add(s);
    }
  }
  for (const k of keys) {
    if (out.has(k)) continue;
    let s = 0;
    while (used.has(s) && s < SLOTS - 1) s++;
    out.set(k, s);
    used.add(s);
  }
  for (const [k, s] of out) memory.set(k, s);
  // a remembered slot now held by another group is forgotten, so it cannot come back doubled
  for (const [k, s] of memory) if (!out.has(k) && [...out.values()].includes(s)) memory.delete(k);
  return out;
}
