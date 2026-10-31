import { describe, expect, it } from "vitest";
import { overtakeMargin, stableOrder } from "../../src/ui/order";

type G = { key: string; count: number };
const g = (key: string, count: number): G => ({ key, count });
const keys = (xs: G[]) => xs.map((x) => x.key);

describe("stableOrder", () => {
  it("with no history, is plain rank order", () => {
    expect(keys(stableOrder([g("a", 9), g("b", 5), g("c", 3)], []))).toEqual(["a", "b", "c"]);
  });

  it("two groups trading a one-message lead do not swap every tick", () => {
    let prev = keys(stableOrder([g("lol", 10), g("w", 9)], []));
    // the counts flip back and forth, as a sliding window makes them do
    for (const [a, b] of [[9, 10], [10, 9], [9, 10], [10, 10]]) {
      prev = keys(stableOrder([g("w", b), g("lol", a)], prev));
      expect(prev).toEqual(["lol", "w"]);
    }
  });

  it("a clear overtake does reorder", () => {
    const prev = ["lol", "w"];
    expect(keys(stableOrder([g("w", 14), g("lol", 10)], prev))).toEqual(["w", "lol"]);
  });

  it("a surging new group enters at its true rank, not at the bottom", () => {
    const prev = ["a", "b", "c"];
    const out = stableOrder([g("new", 30), g("a", 9), g("b", 5), g("c", 3)], prev);
    expect(keys(out)).toEqual(["new", "a", "b", "c"]);
  });

  it("drops groups that left the window and keeps every count untouched", () => {
    const input = [g("a", 7), g("c", 4)];
    const out = stableOrder(input, ["a", "b", "c"]);
    expect(keys(out)).toEqual(["a", "c"]);
    expect(out).toEqual(expect.arrayContaining(input));
    expect(out).toHaveLength(input.length);
  });

  it("never lets a row sit above one that clearly leads it (fuzzed)", () => {
    let seed = 7;
    const rnd = () => ((seed = (seed * 1103515245 + 12345) % 2 ** 31) / 2 ** 31);
    let prev: string[] = [];
    for (let tick = 0; tick < 500; tick++) {
      const groups = Array.from({ length: 1 + Math.floor(rnd() * 8) }, (_, i) =>
        g(`k${Math.floor(rnd() * 10)}_${i % 3}`, 1 + Math.floor(rnd() * 40)),
      ).filter((x, i, xs) => xs.findIndex((y) => y.key === x.key) === i);
      const out = stableOrder(groups, prev);
      expect(new Set(keys(out))).toEqual(new Set(keys(groups)));
      for (let i = 1; i < out.length; i++) {
        expect(out[i].count - out[i - 1].count).toBeLessThan(overtakeMargin(out[i - 1].count));
      }
      prev = keys(out);
    }
  });
});
