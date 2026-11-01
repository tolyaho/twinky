// Dev scores of a few chosen (model, configuration) pairs, broken down by window language — the
// check behind choosing one model for both English and Russian chat. Dev windows only.
//
//   npx tsx web/eval/compare.ts
import type { HybridOptions } from "../src/semantic/hybrid";
import { EVALUATED_OPTIONS as OPTIONS } from "../src/semantic/config"; // what shipped on 2026-10-31
import { DEFAULT_OPTIONS } from "../src/semantic/hybrid";
import { armHybrid, armLexical, hybridTexts, VectorStore } from "./arms";
import { checkFrozen, historicalWindows, realWindows, type Win } from "./data";
import { CANDIDATES } from "./embedders";
import { pool, score, type Pred } from "./score";

checkFrozen();
const dev = [...realWindows().filter((w) => w.split === "dev"), ...historicalWindows()];
const subsets: [string, Win[]][] = [
  ["en (live)", dev.filter((w) => w.split === "dev" && w.language === "en")],
  ["ru (live)", dev.filter((w) => w.language !== "en")],
  ["historical", dev.filter((w) => w.split === "hist")],
  ["all dev", dev],
];
const C = (o: Partial<HybridOptions>): HybridOptions => ({ ...DEFAULT_OPTIONS, ...o });
const pairs: [string, HybridOptions][] = [
  ["minilm-l6", { ...OPTIONS, script: "any" }], // what shipped, but shown every script
  ["minilm-l6", OPTIONS], // what shipped
  ["minilm-l6", C({ method: "center", mergeCenters: true, threshold: 0.75 })],
  ["minilm-l6", C({ method: "center", mergeCenters: true, threshold: 0.75, script: "latin" })],
  ["mxbai-xsmall", C({ method: "center", mergeCenters: true, threshold: 0.75 })],
  ["rubert-tiny2", C({ method: "single", threshold: 0.96 })],
  ["user2-small", C({ method: "center", mergeCenters: true, threshold: 0.95 })],
  ["me5-small", C({ method: "average", threshold: 0.9, minMessages: 3 })],
];
const run = (ws: Win[], arm: (w: Win) => Pred) => pool(ws.map((w) => ({ s: score(w.gold, arm(w)), n: w.messages.length })));
const f = (x: number) => x.toFixed(3);
console.log("".padEnd(16), subsets.map(([n, ws]) => `${n} (${ws.reduce((a, w) => a + w.messages.length, 0)} msgs)`.padEnd(30)).join(""));
console.log("".padEnd(16), subsets.map(() => "b3F1   pairP  false".padEnd(30)).join(""));
const line = (name: string, arm: (w: Win) => Pred) =>
  console.log(
    name.padEnd(16),
    subsets.map(([, ws]) => {
      const s = run(ws, arm);
      return `${f(s.bcubed.f1)}  ${f(s.pairs.p)}  ${s.falseMerges}/${s.shown}`.padEnd(30);
    }).join(""),
  );
line("A lexical", armLexical);
line("C0 no model", (w) => armHybrid(w, () => new Float32Array([1]), C({ threshold: 1.01 })));
for (const [key, o] of pairs) {
  const store = new VectorStore(CANDIDATES.find((c) => c.key === key)!);
  await store.ensure(dev.flatMap(hybridTexts));
  line(key + (o.script === "latin" ? "+latin" : ""), (w) => armHybrid(w, store.get, o));
}
