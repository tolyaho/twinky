// A follow-up to the semantic evaluation (evals/semantic/README.md), for two defects seen on the
// live board, each with one candidate rule. Everything else is the configuration evaluated there.
//   oneWordStems — a group made only of one-word messages, joined by the model on spelling rather
//                  than meaning: keep together only the spellings of one word (src/semantic/hybrid.ts)
//   vocatives    — "chat", "chatter", "chatters" left out of what is compared: a 15-message false
//                  merge was held together by "chatter" (src/semantic/prep.ts)
//
// Each is decided on DEV, by the evaluation's own rule: adopt if dev B-cubed F1 does not fall and
// dev false merges stay within the 10 % cap. The test split was already scored once, for the
// evaluated configuration, and its examples are how these defects were found — so a test score
// after either change is NOT a fresh held-out result. `--test` prints it, labelled as such.
// evals/semantic/followup.md reads the numbers.
//
//   npx tsx web/eval/followup.ts [--test] [--write]
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import { EVALUATED_OPTIONS as OPTIONS } from "../src/semantic/config";
import { prepAll, textsToEmbed, type HybridOptions } from "../src/semantic/hybrid";
import { armHybrid, hybridTexts, VectorStore } from "./arms";
import { checkFrozen, historicalWindows, realWindows, ROOT, type Win } from "./data";
import { CANDIDATES } from "./embedders";
import { pool, score, type Score } from "./score";

const showTest = process.argv.includes("--test");
const write = process.argv.includes("--write");
checkFrozen();
const real = realWindows();
const dev = [...real.filter((w) => w.split === "dev"), ...historicalWindows()];
const test = real.filter((w) => w.split === "test");

const store = new VectorStore(CANDIDATES.find((c) => c.key === "minilm-l6")!);
await store.ensure(
  [...dev, ...test].flatMap((w) => [...hybridTexts(w), ...textsToEmbed(prepAll(w.messages, w.channel, { vocatives: true }))]),
);
store.save();

const ARMS: { key: string; label: string; o: HybridOptions }[] = [
  { key: "evaluated", label: "C hybrid, as evaluated", o: OPTIONS },
  { key: "oneWordStems", label: "C + one-word groups by stem", o: { ...OPTIONS, oneWordStems: true } },
  { key: "vocatives", label: "C + no chat/chatter in texts", o: { ...OPTIONS, vocatives: true } },
];

const run = (ws: Win[], o: HybridOptions): Score =>
  pool(ws.map((w) => ({ s: score(w.gold, armHybrid(w, store.get, o)), n: w.messages.length })));
const row = (s: Score) => ({
  pairP: +s.pairs.p.toFixed(3),
  pairR: +s.pairs.r.toFixed(3),
  pairF1: +s.pairs.f1.toFixed(3),
  b3F1: +s.bcubed.f1.toFixed(3),
  shown: s.shown,
  falseMerges: s.falseMerges,
  falseMergeShare: +s.falseMergeShare.toFixed(3),
});
const fmt = (r: ReturnType<typeof row>) =>
  `pairP ${r.pairP.toFixed(3)}  pairR ${r.pairR.toFixed(3)}  pairF1 ${r.pairF1.toFixed(3)}  B3F1 ${r.b3F1.toFixed(3)}  ` +
  `false merges ${r.falseMerges}/${r.shown} (${(100 * r.falseMergeShare).toFixed(0)}%)`;

const out: Record<string, unknown> = {
  question: "does either candidate rule (oneWordStems, vocatives) remove false merges without losing dev B-cubed F1?",
  rule: "adopt if dev B-cubed F1 does not fall and dev false merges stay <= 10%",
  testNote: "the test split was scored before these changes and its examples motivated them: not a fresh held-out result",
  dev: {} as Record<string, unknown>,
  /** the rule applied to unrounded scores: rounding hides a fall of 0.0002 */
  decision: {} as Record<string, { b3F1: number; falseMergeShare: number; adopt: boolean }>,
  devWindows: {} as Record<string, Record<string, number>>,
  ...(showTest ? { testAlreadySeen: {} as Record<string, unknown> } : {}),
};

console.log(`dev: ${dev.map((w) => w.name).join(", ")}\n`);
const base = run(dev, OPTIONS);
for (const a of ARMS) {
  const s = run(dev, a.o);
  const r = row(s);
  (out.dev as Record<string, unknown>)[a.key] = r;
  console.log(`DEV   ${a.label.padEnd(30)} ${fmt(r)}`);
  if (a.key !== "evaluated") {
    const adopt = s.bcubed.f1 >= base.bcubed.f1 && s.falseMergeShare <= 0.1;
    (out.decision as Record<string, unknown>)[a.key] = { b3F1: +s.bcubed.f1.toFixed(6), falseMergeShare: +s.falseMergeShare.toFixed(4), adopt };
  }
}
console.log(`\nrule, on unrounded dev scores (evaluated B3F1 ${base.bcubed.f1.toFixed(6)}):`);
for (const [k, d] of Object.entries(out.decision as Record<string, { b3F1: number; adopt: boolean }>))
  console.log(`  ${k.padEnd(14)} B3F1 ${d.b3F1.toFixed(6)}  ${d.adopt ? "adopt" : "do not adopt"}`);
console.log(`\nper dev window, B-cubed F1 (${ARMS.map((a) => a.key).join(" / ")}), where they differ:`);
for (const w of dev) {
  const f = ARMS.map((x) => score(w.gold, armHybrid(w, store.get, x.o)).bcubed.f1);
  (out.devWindows as Record<string, Record<string, number>>)[w.name] = Object.fromEntries(ARMS.map((x, i) => [x.key, +f[i].toFixed(3)]));
  if (f.some((v) => Math.abs(v - f[0]) > 1e-9)) console.log(`  ${w.name.padEnd(36)} ${f.map((v) => v.toFixed(3)).join(" / ")}`);
}
if (showTest) {
  console.log("\nTEST — already scored before this change; not a fresh held-out result:");
  for (const a of ARMS) {
    const r = row(run(test, a.o));
    (out.testAlreadySeen as Record<string, unknown>)[a.key] = r;
    console.log(`TEST  ${a.label.padEnd(30)} ${fmt(r)}`);
  }
}
if (write) writeFileSync(join(ROOT, "evals/semantic/followup.json"), JSON.stringify(out, null, 1) + "\n");
