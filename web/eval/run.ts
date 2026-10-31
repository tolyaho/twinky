// The semantic-grouping evaluation. Scores the arms on the same windows, chooses every free
// parameter on the dev split only (rule below, fixed before any run), then reports the chosen
// configuration of each arm on the held-out test split, once.
//
//   npx tsx web/eval/run.ts [--models minilm-l6,bge-small] [--write]
//
// Selection rule: highest pooled dev B-cubed F1 among configurations whose pooled dev share of
// false merges is at most 10 %. B-cubed rather than pairwise, because pairwise F1 is dominated by
// the one or two biggest groups in a window; the false-merge cap, because for this product a
// confident wrong group is worse than a missing one.
import { writeFileSync } from "node:fs";
import { join } from "node:path";
import type { ClusterOptions, Method } from "../src/semantic/cluster";
import { MODEL, OPTIONS as SHIPPED } from "../src/semantic/config";
import { DEFAULT_OPTIONS, prepAll, type HybridOptions } from "../src/semantic/hybrid";
import { armEmbed, armHybrid, armLexical, hybridTexts, VectorStore } from "./arms";
import { checkFrozen, contrastWindows, historicalWindows, realWindows, recordedOpenAI, ROOT, type Win } from "./data";
import { CANDIDATES } from "./embedders";
import { pool, score, type Gold, type Pred, type Score } from "./score";

const args = process.argv.slice(2);
const opt = (k: string) => {
  const i = args.indexOf(k);
  return i >= 0 ? args[i + 1] : undefined;
};
const modelKeys = (opt("--models") ?? "minilm-l6").split(",");
const write = args.includes("--write");
// The test split is printed only when asked, once the model and method have been chosen on dev.
const showTest = args.includes("--test");

checkFrozen();
const real = realWindows();
const dev = [...real.filter((w) => w.split === "dev"), ...historicalWindows()];
const test = real.filter((w) => w.split === "test");
const contrast = contrastWindows();
const all = [...dev, ...test, ...contrast];

/** Only messages the fast path hands to the model: where grouping by meaning is decided. */
function textOnly(w: Win): Gold {
  const prepped = prepAll(w.messages, w.channel);
  return new Map([...w.gold].filter(([id]) => prepped.find((m) => m.id === id)!.prep.kind === "text"));
}

function evaluate(ws: Win[], arm: (w: Win) => Pred, subset?: (w: Win) => Gold): Score {
  return pool(ws.map((w) => ({ s: score(subset ? subset(w) : w.gold, arm(w)), n: w.messages.length })));
}

const fmt = (s: Score) =>
  [
    s.pairs.p, s.pairs.r, s.pairs.f1, s.bcubed.p, s.bcubed.r, s.bcubed.f1,
  ].map((x) => x.toFixed(3)).join("  ") +
  `   shown ${String(s.shown).padStart(3)}  false ${String(s.falseMerges).padStart(2)} (${(100 * s.falseMergeShare).toFixed(0).padStart(2)}%)` +
  `  frag ${s.fragmentation.toFixed(2)}  covered ${s.goldCovered.toFixed(2)}  noise-kept ${s.noiseKept.toFixed(2)}`;
const HEAD = "                                   pairP  pairR  pairF1 b3P    b3R    b3F1";

function grid(method: Method): ClusterOptions[] {
  const out: ClusterOptions[] = [];
  // 0.30 … 0.95 by 0.05, then finer at the top, where anisotropic models put everything
  const ts = [...Array.from({ length: 14 }, (_, i) => +(0.3 + i * 0.05).toFixed(2)), 0.96, 0.97, 0.98];
  const qs = method === "average" ? [undefined] : [undefined, 0.9, 0.95, 0.98];
  for (const threshold of ts)
    for (const adaptiveQuantile of qs)
      for (const minMessages of [2, 3])
        for (const mergeCenters of method === "center" ? [false, true] : [false])
          out.push({ method, threshold, adaptiveQuantile, minMessages, minAuthors: 2, refine: 2, mergeCenters });
  return out;
}

function choose<T>(configs: T[], run: (c: T) => Score): { c: T; s: Score } | null {
  let best: { c: T; s: Score } | null = null;
  for (const c of configs) {
    const s = run(c);
    if (s.falseMergeShare > 0.1) continue;
    if (!best || s.bcubed.f1 > best.s.bcubed.f1 + 1e-9) best = { c, s };
  }
  return best;
}

const describe = (o: ClusterOptions) =>
  `${o.method}${o.mergeCenters ? "+merge" : ""} t=${o.threshold}${o.adaptiveQuantile ? ` q=${o.adaptiveQuantile}` : ""} min=${o.minMessages}`;

const results: Record<string, unknown> = { rule: "max dev B-cubed F1 s.t. dev false-merge share <= 10%", models: {} };

console.log(`dev: ${dev.map((w) => w.name).join(", ")}`);
console.log(`test: ${test.map((w) => w.name).join(", ")}${showTest ? "" : " (not scored: pass --test)"}\n`);

const report = (label: string, arm: (w: Win) => Pred) => {
  if (!showTest) return;
  console.log(`  ${label.padEnd(33)}${fmt(evaluate(test, arm))}`);
  console.log(`  ${"  (text-only subset)".padEnd(33)}${fmt(evaluate(test, arm, textOnly))}`);
};

// A has no free parameters; neither does C0, the hybrid's fast path with no model at all —
// reactions by family, and identical texts from several chatters. What C adds over C0 is what
// the embeddings themselves contribute.
const noModel: HybridOptions = { ...DEFAULT_OPTIONS, threshold: 1.01 };
const armFast = (w: Win) => armHybrid(w, () => new Float32Array([1]), noModel);
console.log("DEV   " + HEAD.slice(6));
console.log(`  ${"A lexical (shipped)".padEnd(33)}${fmt(evaluate(dev, armLexical))}`);
console.log(`  ${"C0 fast path, no model".padEnd(33)}${fmt(evaluate(dev, armFast))}`);
console.log(`  ${"  (text-only subset) A".padEnd(33)}${fmt(evaluate(dev, armLexical, textOnly))}`);
console.log(`  ${"  (text-only subset) C0".padEnd(33)}${fmt(evaluate(dev, armFast, textOnly))}`);
if (showTest) console.log("TEST  " + HEAD.slice(6));
report("A lexical (shipped)", armLexical);
report("C0 fast path, no model", armFast);

// The agreement of two independent labellings: the ceiling any method can expect.
const doubled = test.filter((w) => w.gold2);
if (doubled.length && showTest) {
  const agree = pool(
    doubled.map((w) => {
      const p: Pred = new Map([...w.gold2!].map(([id, v]) => [id, v === "x" || v === "unsure" ? null : v]));
      return { s: score(w.gold, p), n: w.messages.length };
    }),
  );
  console.log(`  ${"labeller 2 vs labeller 1".padEnd(33)}${fmt(agree)}`);
}

for (const key of modelKeys) {
  const c = CANDIDATES.find((x) => x.key === key);
  if (!c) throw new Error(`unknown model ${key}`);
  const store = new VectorStore(c);
  await store.ensure(all.flatMap((w) => [...w.messages.map((m) => m.text), ...hybridTexts(w)]));
  store.save();

  const bBest = (["single", "average", "center"] as Method[])
    .map((m) => choose(grid(m), (o) => evaluate(dev, (w) => armEmbed(w, store.get, o))))
    .filter((x): x is NonNullable<typeof x> => x !== null)
    .sort((a, b) => b.s.bcubed.f1 - a.s.bcubed.f1);
  const bSingle = choose(grid("single"), (o) => evaluate(dev, (w) => armEmbed(w, store.get, o)));
  const cBest = (["single", "average", "center"] as Method[]).map((m) => ({
    m,
    best: choose(
      // an English-only model is shown only Latin-script text (see `embeddable`)
      grid(m).map((g): HybridOptions => ({ ...DEFAULT_OPTIONS, ...g, script: c.langs === "en" ? "latin" : "any" })),
      (o) => evaluate(dev, (w) => armHybrid(w, store.get, o)),
    ),
  }));

  console.log(`\n${c.key} (${c.mb} MB)  — configurations chosen on dev:`);
  console.log("DEV   " + HEAD.slice(6));
  if (bSingle) console.log(`  ${`B single (${describe(bSingle.c)})`.padEnd(33)}${fmt(bSingle.s)}`);
  if (bBest[0]) console.log(`  ${`B best (${describe(bBest[0].c)})`.padEnd(33)}${fmt(bBest[0].s)}`);
  for (const { m, best } of cBest) {
    if (!best) {
      console.log(`  C ${m}: no configuration under the false-merge cap`);
      continue;
    }
    console.log(`  ${`C ${describe(best.c)}`.padEnd(33)}${fmt(best.s)}`);
    console.log(`  ${"  (text-only subset)".padEnd(33)}${fmt(evaluate(dev, (w) => armHybrid(w, store.get, best.c), textOnly))}`);
  }

  if (showTest) console.log("TEST  " + HEAD.slice(6));
  if (bBest[0]) report(`B ${describe(bBest[0].c)}`, (w) => armEmbed(w, store.get, bBest[0].c));
  const cTop = cBest.filter((x) => x.best).sort((a, b) => b.best!.s.bcubed.f1 - a.best!.s.bcubed.f1)[0]?.best;
  for (const { best } of cBest) if (best) report(`C ${describe(best.c)}${best === cTop ? " *" : ""}`, (w) => armHybrid(w, store.get, best.c));
  if (cTop) {
    console.log("CONTRAST (constructed, not real chat)");
    console.log(`  ${"A lexical".padEnd(33)}${fmt(evaluate(contrast, armLexical))}`);
    console.log(`  ${`C ${describe(cTop.c)}`.padEnd(33)}${fmt(evaluate(contrast, (w) => armHybrid(w, store.get, cTop.c)))}`);
  }
  (results.models as Record<string, unknown>)[c.key] = {
    mb: c.mb,
    B: bBest[0] && { config: bBest[0].c, dev: bBest[0].s, ...(showTest ? { test: evaluate(test, (w) => armEmbed(w, store.get, bBest[0].c)) } : {}) },
    C: cBest.map(({ m, best }) => ({ method: m, config: best?.c, dev: best?.s, ...(showTest && best ? { test: evaluate(test, (w) => armHybrid(w, store.get, best.c)) } : {}) })),
  };
}

// The configuration that ships (src/semantic/config.ts), scored on every split.
{
  const c = CANDIDATES.find((x) => x.repo === MODEL.repo)!;
  const store = new VectorStore(c);
  await store.ensure(all.flatMap(hybridTexts));
  const arm = (w: Win) => armHybrid(w, store.get, SHIPPED);
  console.log(`\nSHIPPED: ${c.key}, ${describe(SHIPPED)}, script=${SHIPPED.script}`);
  console.log(`  ${"dev".padEnd(33)}${fmt(evaluate(dev, arm))}`);
  if (showTest) {
    console.log(`  ${"test".padEnd(33)}${fmt(evaluate(test, arm))}`);
    console.log(`  ${"test (text-only subset)".padEnd(33)}${fmt(evaluate(test, arm, textOnly))}`);
    for (const w of test) console.log(`    ${w.name.padEnd(31)}${fmt(evaluate([w], arm))}`);
    for (const w of test) console.log(`    ${("A " + w.name).padEnd(31)}${fmt(evaluate([w], armLexical))}`);
    results.shipped = { model: c.key, config: SHIPPED, dev: evaluate(dev, arm), test: evaluate(test, arm), testTextOnly: evaluate(test, arm, textOnly) };
    results.lexical = { dev: evaluate(dev, armLexical), test: evaluate(test, armLexical), testTextOnly: evaluate(test, armLexical, textOnly) };
    results.fastPath = { dev: evaluate(dev, armFast), test: evaluate(test, armFast), testTextOnly: evaluate(test, armFast, textOnly) };
  }
}

// The historical arm with the vectors it was originally scored with: a check that this harness
// reproduces evals/grouping (single-link, no floors, C@0.40 pooled F1 0.583 in its README).
const openai = recordedOpenAI();
if (openai.size) {
  const hist = historicalWindows();
  const o: ClusterOptions = { method: "single", threshold: 0.4, minMessages: 1, minAuthors: 1 };
  const s = pool(hist.map((w) => ({ s: score(w.gold, armEmbed(w, (t) => openai.get(t), o)), n: w.messages.length })));
  console.log(`\nreproduction: text-embedding-3-small single-link 0.40, historical windows: pair P ${s.pairs.p.toFixed(3)} R ${s.pairs.r.toFixed(3)} F1 ${s.pairs.f1.toFixed(3)}`);
  results.reproduction = s.pairs;
}

console.log("\nLabels are model-drafted (reviewed: false). Every number above inherits that.");
if (write) writeFileSync(join(ROOT, "evals/semantic/results.json"), JSON.stringify(results, null, 1) + "\n");
