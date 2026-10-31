// Cut evaluation windows out of a raw capture (see capture.mjs). One window per channel: the
// busiest 60 s, or the busiest 30 s when 60 s holds more than a person can label carefully, or a
// deliberately quiet stretch for the quiet-chat case. Windows are written without any labels;
// labelling happens separately, before any grouping method is tuned.
//
//   npx tsx web/eval/select-windows.ts <capture-dir> <out-dir>
import { mkdirSync, readFileSync, readdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

interface Row {
  id: string;
  ts_ms: number;
  author: string;
  bot: boolean;
  text: string;
}

const [capture, out] = process.argv.slice(2);
const CAP = 220; // messages per window: enough to show structure, few enough to label by reading
mkdirSync(out, { recursive: true });

function busiest(rows: Row[], spanMs: number): [number, number] {
  let best = [0, 0] as [number, number];
  let j = 0;
  for (let i = 0; i < rows.length; i++) {
    while (rows[i].ts_ms - rows[j].ts_ms > spanMs) j++;
    if (i - j + 1 > best[1] - best[0]) best = [j, i + 1];
  }
  return best;
}

const summary: Record<string, unknown>[] = [];
for (const f of readdirSync(capture).filter((f) => f.endsWith(".jsonl")).sort()) {
  const channel = f.replace(/\.jsonl$/, "");
  const rows: Row[] = readFileSync(join(capture, f), "utf8")
    .split("\n")
    .filter(Boolean)
    .map((l) => JSON.parse(l))
    .sort((a: Row, b: Row) => a.ts_ms - b.ts_ms || a.id.localeCompare(b.id));
  if (rows.length < 25) {
    summary.push({ channel, total: rows.length, skipped: "too quiet to form a window" });
    continue;
  }
  let span = 60_000;
  let [a, b] = busiest(rows, span);
  if (b - a > CAP) {
    span = 30_000;
    [a, b] = busiest(rows, span);
  }
  if (b - a > CAP) a = b - CAP; // still too busy: the most recent CAP messages of that 30 s
  let kind = span === 60_000 ? "60s" : "30s";
  if (b - a < 40) {
    // a quiet channel: take a whole 5-minute stretch instead, as the 5m window would show it
    span = 300_000;
    [a, b] = busiest(rows, span);
    kind = "5m-quiet";
  }
  const msgs = rows.slice(a, b);
  const cyr = msgs.filter((m) => /[Ѐ-ӿ]/.test(m.text)).length / msgs.length;
  const name = `${channel}_${new Date(msgs[0].ts_ms).toISOString().slice(0, 16).replace(":", "")}`;
  writeFileSync(
    join(out, `${name}.json`),
    JSON.stringify({ window: name, channel, kind, language: cyr > 0.5 ? "ru" : cyr > 0.1 ? "mixed" : "en", messages: msgs }, null, 1),
  );
  summary.push({ channel, total: rows.length, window: name, kind, n: msgs.length, authors: new Set(msgs.map((m) => m.author)).size, cyrillic: +cyr.toFixed(2) });
}
console.table(summary);
