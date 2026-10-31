// How steady the board is, recount by recount, and whether its labels are what chat said. The
// page's own groupers run here — the word rules (lexicalGrouper) and the shipped SemanticGrouper,
// fed by a worker that answers at once from the evaluation's vectors — over real chat replayed at
// its own timestamps: a 60 s window recounted every 1.5 s, as on the board. Nothing is tuned on
// this; it is a description of the configuration that ships.
//
//   moved      of messages grouped at one recount and still in the window at the next, the share
//              now in a different group
//   dropped    ... the share now in no group
//   relabelled of groups present at two consecutive recounts, the share whose label changed
//   faithful   topics whose label is the start of one of its own messages (it should be all)
//
//   npx tsx web/eval/stability.ts [--write]
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import type { ChatEvent } from "../src/cluster/types";
import { lexicalGrouper } from "../src/engine/session";
import { clusterItems, coherence, type Item } from "../src/semantic/cluster";
import { MODEL, OPTIONS } from "../src/semantic/config";
import { prepAll, textsToEmbed } from "../src/semantic/hybrid";
import { SemanticGrouper, resetSharedWorker, type WorkerLike } from "../src/semantic/live";
import { isBotLogin } from "../src/semantic/prep";
import type { FromWorker, ToWorker } from "../src/semantic/protocol";
import { VectorStore } from "./arms";
import { checkFrozen, realWindows, ROOT } from "./data";
import { CANDIDATES } from "./embedders";

const WINDOW_MS = 60_000;
const TICK_MS = 1_500;
const write = process.argv.includes("--write");
checkFrozen();

interface Source {
  name: string;
  split: string;
  channel: string;
  events: ChatEvent[];
}
const replayRows: { id: string; ts_ms: number; login: string; text: string }[] = JSON.parse(
  readFileSync(join(ROOT, "web/src/data/replay.json"), "utf8"),
);
const sources: Source[] = [
  {
    name: "replay (stableronaldo)",
    split: "replay",
    channel: "stableronaldo",
    events: replayRows.map((r) => ({ id: r.id, ts_ms: r.ts_ms, author: r.login, text: r.text, bot: isBotLogin(r.login) })),
  },
  // the captures long enough to recount many times (the others span 20-60 s)
  ...realWindows()
    .filter((w) => w.messages.at(-1)!.ts_ms - w.messages[0].ts_ms >= 120_000)
    .map((w) => ({ name: w.name, split: w.split, channel: w.channel, events: w.messages })),
];

const store = new VectorStore(CANDIDATES.find((c) => c.key === "minilm-l6")!);
await store.ensure(sources.flatMap((s) => textsToEmbed(prepAll(s.events, s.channel))));
store.save();

/** The real worker's protocol, answered synchronously from the evaluation's vectors. */
function instantWorker(): WorkerLike {
  const w: WorkerLike = {
    onmessage: null,
    onerror: null,
    postMessage(m: ToWorker) {
      const emit = (r: FromWorker) => w.onmessage?.({ data: r } as MessageEvent<FromWorker>);
      if (m.type === "init") emit({ type: "ready", device: "wasm", loadMs: 0 });
      if (m.type !== "work") return;
      const items: Item[] = m.items.map((i) => ({ key: i.key, vec: store.get(i.key)!, weight: i.weight, authors: new Set(i.authors) }));
      const clusters = clusterItems(items, m.options).map((g) => ({ keys: g.map((i) => items[i].key), coherence: coherence(items, g) }));
      emit({ type: "result", epoch: m.epoch, seq: m.seq, clusters, waiting: [], embedMs: 0, clusterMs: 0 });
    },
  };
  return w;
}

interface Board {
  groups: { key: string; label: string; rule: string; event_ids: string[] }[];
}
interface Tally {
  carried: number;
  moved: number;
  dropped: number;
  pairs: number;
  relabelled: number;
  topics: number;
  faithful: number;
  recounts: number;
}
const zero = (): Tally => ({ carried: 0, moved: 0, dropped: 0, pairs: 0, relabelled: 0, topics: 0, faithful: 0, recounts: 0 });

function run(s: Source, group: (w: ChatEvent[]) => Board, t: Tally) {
  const events = [...s.events].sort((a, b) => a.ts_ms - b.ts_ms);
  const text = new Map(events.map((e) => [e.id, e.text.replace(/^(?:@\w+[\s,:]*)+/, "").replace(/\s+/g, " ").trim()]));
  let prev: Board | null = null;
  for (let now = events[0].ts_ms + TICK_MS; now <= events.at(-1)!.ts_ms + TICK_MS; now += TICK_MS) {
    const window = events.filter((e) => e.ts_ms > now - WINDOW_MS && e.ts_ms <= now);
    if (!window.length) continue;
    const board = group(window);
    t.recounts++;
    const at = new Map<string, string>();
    for (const g of board.groups) for (const id of g.event_ids) at.set(id, g.key);
    if (prev) {
      const live = new Set(window.map((e) => e.id));
      const label = new Map(board.groups.map((g) => [g.key, g.label]));
      for (const g of prev.groups) {
        for (const id of g.event_ids) {
          if (!live.has(id)) continue; // left the window: not instability
          t.carried++;
          const k = at.get(id);
          if (k === undefined) t.dropped++;
          else if (k !== g.key) t.moved++;
        }
        if (label.has(g.key)) {
          t.pairs++;
          if (label.get(g.key) !== g.label) t.relabelled++;
        }
      }
    }
    for (const g of board.groups) {
      if (g.rule !== "topic" && g.rule !== "question") continue;
      t.topics++;
      const stem = g.label.replace(/…$/, "");
      if (g.event_ids.some((id) => text.get(id)!.startsWith(stem))) t.faithful++;
    }
    prev = board;
  }
}

const rows: Record<string, Record<string, Tally>> = {};
for (const s of sources) {
  const lex = zero(), sem = zero();
  run(s, (w) => lexicalGrouper.group(w) as Board, lex);
  resetSharedWorker();
  const g = new SemanticGrouper(s.channel, MODEL, OPTIONS, instantWorker);
  run(s, (w) => g.group(w) as Board, sem);
  g.stop();
  rows[s.name] = { lexical: lex, hybrid: sem, split: s.split as never };
}

const pct = (a: number, b: number) => (b ? `${((100 * a) / b).toFixed(1)}%` : "—");
const sum = (names: string[], arm: "lexical" | "hybrid"): Tally =>
  names.reduce((acc, n) => {
    const r = rows[n][arm];
    for (const k of Object.keys(acc) as (keyof Tally)[]) acc[k] += r[k];
    return acc;
  }, zero());
console.log(`window ${WINDOW_MS / 1000}s, recount every ${TICK_MS / 1000}s\n`);
console.log("source".padEnd(36), "arm".padEnd(8), "recounts  moved    dropped  relabelled  topic labels faithful");
const line = (name: string, arm: "lexical" | "hybrid", r: Tally) =>
  console.log(
    name.padEnd(36),
    arm.padEnd(8),
    String(r.recounts).padEnd(9),
    pct(r.moved, r.carried).padEnd(8),
    pct(r.dropped, r.carried).padEnd(8),
    pct(r.relabelled, r.pairs).padEnd(11),
    arm === "hybrid" ? `${r.faithful}/${r.topics}` : "",
  );
for (const n of Object.keys(rows)) for (const arm of ["lexical", "hybrid"] as const) line(n, arm, rows[n][arm]);
const all = Object.keys(rows);
for (const arm of ["lexical", "hybrid"] as const) line("ALL", arm, sum(all, arm));

if (write) {
  const out = { windowMs: WINDOW_MS, tickMs: TICK_MS, sources: rows, all: { lexical: sum(all, "lexical"), hybrid: sum(all, "hybrid") } };
  writeFileSync(join(ROOT, "evals/semantic/stability.json"), JSON.stringify(out, null, 1) + "\n");
}
