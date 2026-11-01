// How wide a timeline slice should be (src/ui/slices.ts, bucketFor), checked on real chat.
//
// The widths shipped were picked first, by looking at the chart; this script checks them on the
// labelled windows of evals/semantic, which are real chat at the three lengths the board offers
// (30 s, 1 min, 5 min). It is a display choice, not a model choice: nothing here is scored
// against the labels, they only say which messages form the leading group. They are
// model-drafted (evals/semantic/LABELING.md), so "leading group" means "as drafted".
//
// For each width it measures, over the windows of that length:
//   slices  — complete slices across the window (fewer than 10 and a burst is one or two points)
//   empty   — share of the leading group's slices with no message in them, counted from its first
//             message to its last (a line that is mostly zeros reads as noise, not as a trend)
//   third   — the same for the third-largest group: the chart draws up to three group lines, and
//             this is the sparsest of them (added after the first run, see below)
//   perSlice — all-chat messages per slice (the strip above the group lines)
// A width is acceptable when it gives at least 10 slices and the leading group is empty in at most
// half its slices, as the median over the windows of that length. The check passes when the
// shipped width is acceptable.
//
// Said plainly: the first run of this script also printed the *finest* acceptable width (1 s, 3 s,
// 15 s) and "shipped differs". The shipped widths were kept, not moved to those: they are
// acceptable at every length, and at the finest acceptable widths the third line is empty in
// about half its slices or more (57 %, 49 %, 58 %), where at the shipped ones it is 29 %, 31 %,
// 47 %. The third-line column was added to show that, after the first run.
//
//   npx tsx web/eval/timeline-resolution.ts [--write]
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { bucketFor } from "../src/ui/slices";
import { ROOT, realWindows, type Win } from "./data";

const write = process.argv.includes("--write");

const LENGTHS = [
  { kind: "30s", ms: 30_000, widths: [1_000, 2_000, 3_000, 5_000, 10_000] },
  { kind: "60s", ms: 60_000, widths: [2_000, 3_000, 5_000, 10_000, 15_000] },
  { kind: "5m-quiet", ms: 300_000, widths: [5_000, 10_000, 15_000, 20_000, 30_000, 60_000] },
];
const MIN_SLICES = 10;
const MAX_EMPTY = 0.5;

const median = (xs: number[]) => {
  const s = [...xs].sort((a, b) => a - b);
  return s.length ? (s.length % 2 ? s[(s.length - 1) / 2] : (s[s.length / 2 - 1] + s[s.length / 2]) / 2) : NaN;
};

/** The labelled groups, largest first (each from at least two chatters, as the labels require). */
function ranked(w: Win): number[][] {
  const by = new Map<string, number[]>();
  for (const m of w.messages) {
    const v = w.gold.get(m.id);
    if (!v || v === "x" || v === "unsure") continue;
    (by.get(v) ?? by.set(v, []).get(v)!).push(m.ts_ms);
  }
  return [...by.values()].sort((a, b) => b.length - a.length);
}

/** Share of a group's slices, from its first message to its last, with nothing in them. */
function emptyShare(times: number[], start: number, b: number, slices: number): number {
  if (!times.length) return NaN;
  const lo = Math.max(0, Math.floor((Math.min(...times) - start) / b));
  const hi = Math.min(slices - 1, Math.floor((Math.max(...times) - start) / b));
  if (hi < lo) return NaN;
  const counts = new Array(hi - lo + 1).fill(0);
  for (const t of times) {
    const i = Math.floor((t - start) / b);
    if (i >= lo && i <= hi) counts[i - lo]++;
  }
  return counts.filter((c) => c === 0).length / counts.length;
}

function measure(w: Win, windowMs: number, b: number) {
  const ts = w.messages.map((m) => m.ts_ms);
  const end = Math.max(...ts);
  const start = end - windowMs;
  const slices = Math.floor(windowMs / b);
  const all = new Array(slices).fill(0);
  for (const t of ts) {
    const i = Math.floor((t - start) / b);
    if (i >= 0 && i < slices) all[i]++;
  }
  const groups = ranked(w);
  return {
    slices,
    empty: emptyShare(groups[0] ?? [], start, b, slices),
    // the chart draws up to three group lines; the third is the sparsest of them
    third: emptyShare(groups[2] ?? [], start, b, slices),
    perSlice: ts.filter((t) => t > start).length / slices,
  };
}

const windows = realWindows();
let failed = false;
const out: Record<string, unknown> = {
  rule: `a width is acceptable with >= ${MIN_SLICES} slices and the leading group empty in <= ${MAX_EMPTY * 100}% of its slices (median over windows of that length); the check passes when the shipped width is acceptable`,
  note: "display check on the real windows of evals/semantic; labels (model-drafted) only identify the leading group; nothing is scored",
  lengths: {} as Record<string, unknown>,
};

for (const L of LENGTHS) {
  const ws = windows.filter((w) => w.kind === L.kind);
  const shipped = bucketFor(L.ms);
  console.log(`\n${L.kind} window — ${ws.length} real windows (${ws.map((w) => w.channel).join(", ")}); shipped ${shipped / 1000}s`);
  console.log("  width   slices   leading group empty   3rd group empty   all-chat msgs/slice");
  const rows = L.widths.map((b) => {
    const m = ws.map((w) => measure(w, L.ms, b));
    const r = {
      widthMs: b,
      slices: m[0]?.slices ?? Math.floor(L.ms / b),
      emptyMedian: +median(m.map((x) => x.empty).filter((x) => !Number.isNaN(x))).toFixed(2),
      thirdEmptyMedian: +median(m.map((x) => x.third).filter((x) => !Number.isNaN(x))).toFixed(2),
      perSliceMedian: +median(m.map((x) => x.perSlice)).toFixed(1),
    };
    const pass = r.slices >= MIN_SLICES && r.emptyMedian <= MAX_EMPTY;
    console.log(
      `  ${`${b / 1000}s`.padEnd(7)} ${String(r.slices).padEnd(8)} ${`${(100 * r.emptyMedian).toFixed(0)}%`.padEnd(21)} ` +
        `${`${(100 * r.thirdEmptyMedian).toFixed(0)}%`.padEnd(17)} ${r.perSliceMedian}` +
        `${pass ? "  acceptable" : ""}${b === shipped ? "  ← shipped" : ""}`,
    );
    return { ...r, pass };
  });
  const ok = rows.filter((r) => r.pass).map((r) => r.widthMs);
  const shippedOk = ok.includes(shipped);
  if (!shippedOk) failed = true;
  console.log(`  acceptable: ${ok.map((b) => `${b / 1000}s`).join(", ") || "none"} — shipped ${shipped / 1000}s ${shippedOk ? "passes" : "FAILS"}`);
  (out.lengths as Record<string, unknown>)[L.kind] = { windows: ws.map((w) => w.name), shippedMs: shipped, shippedPasses: shippedOk, acceptableMs: ok, rows };
}

if (write) {
  mkdirSync(join(ROOT, "evals/timeline"), { recursive: true });
  writeFileSync(join(ROOT, "evals/timeline/resolution.json"), JSON.stringify(out, null, 1) + "\n");
}
if (failed) process.exitCode = 1;
