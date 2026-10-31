import { describe, expect, it } from "vitest";
import { clusterItems, coherence, type ClusterOptions, type Item } from "../../src/semantic/cluster";
import { hybridGroups, prepAll, textsToEmbed } from "../../src/semantic/hybrid";

// Unit vectors at chosen angles in a plane (plus a private axis each, so "unrelated" is exact):
// cosine between two of them is cos(angle difference).
function at(deg: number, dims = 8): Float32Array {
  const v = new Float32Array(dims);
  v[0] = Math.cos((deg * Math.PI) / 180);
  v[1] = Math.sin((deg * Math.PI) / 180);
  return v;
}
const item = (key: string, vec: Float32Array, authors: string[] = [key + "-a"], weight = authors.length): Item => ({
  key,
  vec,
  weight,
  authors: new Set(authors),
});
const base: ClusterOptions = { method: "center", threshold: 0.8, minMessages: 2, minAuthors: 2, refine: 2 };
const keys = (items: Item[], groups: number[][]) => groups.map((g) => g.map((i) => items[i].key).sort());

describe("clusterItems", () => {
  // A chain: neighbours are 30° apart (cos 0.87), the ends 120° apart (cos -0.5).
  const chain = [0, 30, 60, 90, 120].map((d) => item(`m${d}`, at(d)));

  it("single linkage chains unrelated messages together through intermediaries", () => {
    const g = clusterItems(chain, { ...base, method: "single" });
    expect(g).toHaveLength(1);
    expect(g[0]).toHaveLength(5);
  });

  it("the center method never puts two messages together that are not both close to the center", () => {
    for (const g of clusterItems(chain, base)) {
      const ks = g.map((i) => chain[i].key);
      for (const a of ks) for (const b of ks) {
        const da = Number(a.slice(1)), db = Number(b.slice(1));
        expect(Math.abs(da - db)).toBeLessThanOrEqual(60);
      }
    }
  });

  it("average linkage does not chain either", () => {
    const g = clusterItems(chain, { ...base, method: "average" });
    expect(g.every((x) => x.length < 5)).toBe(true);
  });

  it("drops a group that comes from one chatter, however many messages", () => {
    const solo = [item("a", at(0), ["u1"], 5), item("b", at(5), ["u1"], 3)];
    expect(clusterItems(solo, base)).toEqual([]);
    const two = [item("a", at(0), ["u1"], 5), item("b", at(5), ["u2"], 1)];
    expect(clusterItems(two, base)).toHaveLength(1);
  });

  it("keeps an identical message from several chatters as a group of one text", () => {
    const g = clusterItems([item("copypasta", at(0), ["u1", "u2", "u3"]), item("other", at(90))], base);
    expect(keys([item("copypasta", at(0)), item("other", at(90))], g)).toEqual([["copypasta"]]);
  });

  it("leaves unrelated messages ungrouped", () => {
    const lonely = [0, 90, 180, 270].map((d) => item(`m${d}`, at(d)));
    expect(clusterItems(lonely, base)).toEqual([]);
  });

  it("the adaptive threshold refuses to group chat that is uniformly similar", () => {
    // everything within 20° of everything: one blob at a fixed 0.8 threshold
    const blob = Array.from({ length: 12 }, (_, i) => item(`m${i}`, at(i * 1.8)));
    expect(clusterItems(blob, base)).toHaveLength(1);
    const adaptive = clusterItems(blob, { ...base, adaptiveQuantile: 0.98 });
    expect(adaptive.every((g) => g.length < 12)).toBe(true);
  });

  it("is deterministic and independent of input order", () => {
    const items = [0, 10, 20, 100, 110, 200].map((d) => item(`m${d}`, at(d)));
    const a = keys(items, clusterItems(items, base));
    const rev = [...items].reverse();
    const b = keys(rev, clusterItems(rev, base));
    expect(new Set(b.map((g) => g.join()))).toEqual(new Set(a.map((g) => g.join())));
  });

  it("coherence is 1 for identical vectors and falls as members spread", () => {
    const tight = [item("a", at(0)), item("b", at(0))];
    const loose = [item("a", at(0)), item("b", at(40))];
    expect(coherence(tight, [0, 1])).toBeCloseTo(1, 5);
    expect(coherence(loose, [0, 1])).toBeLessThan(0.95);
  });
});

describe("hybridGroups", () => {
  const msgs = [
    { id: "1", author: "a", text: "KEKW" },
    { id: "2", author: "b", text: "LMAO" },
    { id: "3", author: "c", text: "Pog" },
    { id: "4", author: "d", text: "his mic is muted" },
    { id: "5", author: "e", text: "we can't hear him" },
    { id: "6", author: "f", text: "1" },
    { id: "7", author: "g", text: "1" },
    { id: "8", author: "h", text: "1" },
    { id: "9", author: "i", text: "100" },
    { id: "10", author: "j", text: "https://example.com/x" },
  ];
  const prepped = prepAll(msgs, "jynxzi");
  // a stand-in model that knows the two audio sentences mean the same thing
  const vec = new Map<string, Float32Array>([
    ["his mic is muted", at(0)],
    ["we can t hear him", at(10)],
  ]);

  it("embeds only messages that carry words, once per distinct text", () => {
    expect(textsToEmbed(prepped).sort()).toEqual(["his mic is muted", "we can t hear him"]);
  });

  it("groups laughter by family, a vote by identity, and meaning by vector", () => {
    const r = hybridGroups(prepped, (t) => vec.get(t));
    const by = new Map(r.groups.map((g) => [g.key, g]));
    expect(by.get("r:laughing")?.ids).toEqual(["1", "2"]);
    expect(by.get("p:1")?.ids).toEqual(["6", "7", "8"]);
    const topic = r.groups.find((g) => g.kind === "topic");
    expect(topic?.ids.sort()).toEqual(["4", "5"]);
    // one Pog is not a hype wave; one "100" is not a vote; links never group
    expect([...by.keys()].some((k) => k.includes("hype") || k === "p:100")).toBe(false);
    expect(r.groups.flatMap((g) => g.ids)).not.toContain("10");
    expect(r.pending).toBe(0);
  });

  it("counts messages it has no vector for as pending, never as grouped", () => {
    const r = hybridGroups(prepped, () => undefined);
    expect(r.pending).toBe(2);
    expect(r.textMessages).toBe(2);
    expect(r.groups.some((g) => g.kind === "topic")).toBe(false);
  });
});
