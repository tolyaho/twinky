import { describe, expect, it } from "vitest";
import type { ChatEvent } from "../../src/cluster/types";
import { SERIES_MAX, SLOTS, assignSlots, bucketFor, buildTimeline, pickSeries } from "../../src/ui/slices";

// a clock-aligned start, so slice boundaries are easy to read: T is a multiple of 60 s
const T = 1_700_000_040_000;
const msg = (id: string, ts: number, author = id): ChatEvent => ({ id, ts_ms: ts, author, text: "x" });
const map = (es: ChatEvent[]) => new Map(es.map((e) => [e.id, e]));

describe("bucketFor", () => {
  it("cuts each window into 10-15 slices", () => {
    expect(bucketFor(30_000)).toBe(3_000);
    expect(bucketFor(60_000)).toBe(5_000);
    expect(bucketFor(300_000)).toBe(20_000);
    for (const w of [30_000, 60_000, 300_000]) {
      const n = w / bucketFor(w);
      expect(n).toBeGreaterThanOrEqual(10);
      expect(n).toBeLessThanOrEqual(15);
    }
  });
});

describe("buildTimeline", () => {
  it("is empty slices, not an invented trend, for an empty window", () => {
    const tl = buildTimeline({ events: new Map(), windowStart: T, windowEnd: T + 60_000, observedMs: 60_000, groups: [], bucketMs: 5_000 });
    expect(tl.total.every((v) => v === 0)).toBe(true);
    expect(tl.series).toEqual([]);
  });

  it("counts real timestamps into clock-aligned slices, the newest still open", () => {
    const end = T + 62_000; // two seconds into a slice
    const es = [msg("a", T + 1_000), msg("b", T + 5_500), msg("c", T + 9_999), msg("d", T + 60_500), msg("e", T + 61_000)];
    const tl = buildTimeline({ events: map(es), windowStart: end - 60_000, windowEnd: end, observedMs: 60_000, groups: [], bucketMs: 5_000 });
    // the slice the window's start cuts through (T, T+5s) is partial: not drawn
    expect(tl.starts[0]).toBe(T + 5_000);
    expect(tl.starts.at(-1)).toBe(T + 60_000);
    expect(tl.open).toBe(true);
    expect(tl.total[0]).toBe(2); // b, c
    expect(tl.total.at(-1)).toBe(2); // d, e — so far
    expect(tl.total.reduce((s, v) => s + v, 0)).toBe(4); // a sat in the cut slice
  });

  it("closes the last slice when the window ends exactly on a boundary", () => {
    const end = T + 60_000;
    const tl = buildTimeline({ events: map([msg("a", T + 59_000)]), windowStart: T, windowEnd: end, observedMs: 60_000, groups: [], bucketMs: 5_000 });
    expect(tl.open).toBe(false);
    expect(tl.starts.at(-1)).toBe(T + 55_000);
    expect(tl.starts).toHaveLength(12);
  });

  it("draws nothing before listening began: unknown, not zero", () => {
    // connected 12 s ago into a 60 s window
    const end = T + 60_000;
    const tl = buildTimeline({ events: map([msg("a", end - 11_000), msg("b", end - 2_000)]), windowStart: T, windowEnd: end, observedMs: 12_000, groups: [], bucketMs: 5_000 });
    expect(tl.starts[0]).toBeGreaterThanOrEqual(end - 12_000);
    expect(tl.starts[0]).toBe(T + 50_000); // the first slice that began after we did
    // a, sent in the slice listening began in, is not drawn rather than drawn as a partial count
    expect(tl.total).toEqual([0, 1]);
  });

  it("is still a timeline in the first seconds: one slice, still filling", () => {
    const end = T + 3_000;
    const tl = buildTimeline({ events: map([msg("a", T + 1_000)]), windowStart: end - 60_000, windowEnd: end, observedMs: 3_000, groups: [], bucketMs: 5_000 });
    expect(tl.starts).toEqual([T]);
    expect(tl.open).toBe(true);
    expect(tl.total).toEqual([1]);
  });

  it("counts each group's own messages, overlapping in time", () => {
    const end = T + 15_000;
    const es = [msg("a1", T + 1_000), msg("b1", T + 2_000), msg("a2", T + 6_000), msg("b2", T + 7_000), msg("b3", T + 11_000), msg("z", T + 12_000)];
    const tl = buildTimeline({
      events: map(es),
      windowStart: T,
      windowEnd: end,
      observedMs: 15_000,
      groups: [
        { key: "A", event_ids: ["a1", "a2"] },
        { key: "B", event_ids: ["b1", "b2", "b3"] },
      ],
      bucketMs: 5_000,
    });
    expect(tl.total).toEqual([2, 2, 2]);
    expect(tl.series).toEqual([
      { key: "A", counts: [1, 1, 0] },
      { key: "B", counts: [1, 1, 1] },
    ]);
  });

  it("ignores members that have left the window", () => {
    const tl = buildTimeline({
      events: map([msg("a", T + 1_000)]),
      windowStart: T,
      windowEnd: T + 5_000,
      observedMs: 5_000,
      groups: [{ key: "A", event_ids: ["a", "gone"] }],
      bucketMs: 5_000,
    });
    expect(tl.series[0].counts).toEqual([1]);
  });

  it("keeps a drawn slice's count when the window moves on", () => {
    const es = Array.from({ length: 40 }, (_, i) => msg(`m${i}`, T + i * 1_500));
    const at = (end: number) =>
      buildTimeline({ events: map(es.filter((e) => e.ts_ms >= end - 30_000 && e.ts_ms <= end)), windowStart: end - 30_000, windowEnd: end, observedMs: 30_000, groups: [], bucketMs: 3_000 });
    const a = at(T + 45_000);
    const b = at(T + 46_500);
    const common = a.starts.filter((s, i) => i < a.starts.length - 1 && b.starts.includes(s));
    expect(common.length).toBeGreaterThan(5);
    for (const s of common) expect(b.total[b.starts.indexOf(s)]).toBe(a.total[a.starts.indexOf(s)]);
  });
});

describe("pickSeries", () => {
  const gs = ["a", "b", "c", "d", "e"].map((key) => ({ key }));
  it("draws the board's leading groups, in its order", () => {
    expect(pickSeries(gs, null).map((g) => g.key)).toEqual(["a", "b", "c"].slice(0, SERIES_MAX));
  });
  it("adds the open group when it is further down", () => {
    expect(pickSeries(gs, "e").map((g) => g.key)).toEqual(["a", "b", "c", "e"]);
    expect(pickSeries(gs, "b").map((g) => g.key)).toEqual(["a", "b", "c"]);
    expect(pickSeries(gs, "gone").map((g) => g.key)).toEqual(["a", "b", "c"]);
  });
});

describe("assignSlots: colour follows the group, not its rank", () => {
  it("keeps a group's colour when the ranking changes, or its label does", () => {
    const mem = new Map<string, number>();
    const first = assignSlots(["a", "b", "c"], mem);
    const swapped = assignSlots(["c", "a", "b"], mem);
    for (const k of ["a", "b", "c"]) expect(swapped.get(k)).toBe(first.get(k));
  });

  it("gives a new group a free colour, and a returning group its old one if still free", () => {
    const mem = new Map<string, number>();
    assignSlots(["a", "b", "c"], mem); // a0 b1 c2
    const next = assignSlots(["a", "c", "d"], mem); // b left; d takes the free slot
    expect(next.get("a")).toBe(0);
    expect(next.get("c")).toBe(2);
    expect(next.get("d")).toBe(1);
    const back = assignSlots(["a", "c", "d", "b"], mem); // b returns; its slot is taken now
    expect(new Set(back.values()).size).toBe(4);
    expect(back.get("b")).toBe(3);
  });

  it("never gives two groups on the chart the same colour", () => {
    const mem = new Map<string, number>();
    for (let r = 0; r < 50; r++) {
      const keys = Array.from({ length: SLOTS }, (_, i) => `k${(r * 3 + i * 7) % 11}`).filter((k, i, a) => a.indexOf(k) === i);
      const s = assignSlots(keys, mem);
      expect(new Set(s.values()).size).toBe(keys.length);
    }
  });
});
