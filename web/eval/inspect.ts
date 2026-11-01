// Look at what a configuration actually does to a dev window: how each labelled group was split
// (or missed), and which shown groups are false merges, with the messages themselves.
// Dev windows by default. `--report` also opens the test split, for describing results after the
// one scored test run — never for changing the method.
//
// The evaluated configuration by default; `--current` looks at what ships now (followup.md).
//
//   npx tsx web/eval/inspect.ts <window name substring> [model] [threshold] [--report] [--current]
import { EVALUATED_OPTIONS, OPTIONS as CURRENT } from "../src/semantic/config";
import { prepAll, type HybridOptions } from "../src/semantic/hybrid";
import { armHybrid, hybridTexts, VectorStore } from "./arms";
import { checkFrozen, contrastWindows, historicalWindows, realWindows } from "./data";
import { CANDIDATES } from "./embedders";

const report = process.argv.includes("--report");
const OPTIONS = process.argv.includes("--current") ? CURRENT : EVALUATED_OPTIONS;
const [needle, modelKey = "minilm-l6", t = "0.75"] = process.argv.slice(2).filter((a) => !a.startsWith("--"));
checkFrozen();
const ws = [...realWindows().filter((w) => report || w.split === "dev"), ...historicalWindows(), ...contrastWindows()].filter((w) =>
  w.name.includes(needle),
);
const store = new VectorStore(CANDIDATES.find((c) => c.key === modelKey)!);
await store.ensure(ws.flatMap((w) => hybridTexts(w, OPTIONS)));
store.save();
const o: HybridOptions = { ...OPTIONS, threshold: Number(t) };

for (const w of ws) {
  const pred = armHybrid(w, store.get, o);
  const prep = new Map(prepAll(w.messages, w.channel, OPTIONS).map((m) => [m.id, m.prep]));
  const text = new Map(w.messages.map((m) => [m.id, m.text]));
  const show = (id: string) => {
    const p = prep.get(id)!;
    return `${JSON.stringify(text.get(id)!.slice(0, 60))}<${p.kind}${p.family ? ":" + p.family : ""}>`;
  };
  console.log(`\n=== ${w.name}  (${w.messages.length} messages)`);
  const gold = new Map<string, string[]>();
  for (const [id, g] of w.gold) if (g !== "x" && g !== "unsure") (gold.get(g) ?? gold.set(g, []).get(g)!).push(id);
  for (const [g, ids] of [...gold].sort((a, b) => b[1].length - a[1].length)) {
    const parts = new Map<string, string[]>();
    for (const id of ids) {
      const k = pred.get(id) ?? "(none)";
      (parts.get(k) ?? parts.set(k, []).get(k)!).push(id);
    }
    console.log(`  gold ${g} (${ids.length})`);
    for (const [k, xs] of [...parts].sort((a, b) => b[1].length - a[1].length))
      console.log(`     ${String(xs.length).padStart(3)} -> ${k.slice(0, 40)}: ${xs.slice(0, 6).map(show).join("  ")}`);
  }
  const byPred = new Map<string, string[]>();
  for (const [id, k] of pred) if (k) (byPred.get(k) ?? byPred.set(k, []).get(k)!).push(id);
  for (const [k, ids] of byPred) {
    const counts = new Map<string, number>();
    for (const id of ids) {
      const g = w.gold.get(id) ?? "?";
      const gg = g === "x" ? `x:${id}` : g;
      counts.set(gg, (counts.get(gg) ?? 0) + 1);
    }
    if (Math.max(...counts.values()) / ids.length < 2 / 3)
      console.log(`  FALSE MERGE ${k.slice(0, 40)} (${ids.length}): ${ids.slice(0, 8).map((id) => `${show(id)}[${w.gold.get(id)}]`).join("  ")}`);
  }
}
