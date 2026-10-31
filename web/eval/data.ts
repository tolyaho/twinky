// Every labelled window the semantic evaluation scores, in one shape:
//   - real windows captured for this evaluation (evals/semantic/windows + labels), dev or test
//   - the two historical windows of evals/grouping (dev only: they shaped the original finding)
//   - the constructed contrast scenes (dev only, never in headline numbers)
import { createHash } from "node:crypto";
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import type { Gold } from "./score";

export const ROOT = fileURLToPath(new URL("../../", import.meta.url));
const SEM = join(ROOT, "evals/semantic");

export interface Msg {
  id: string;
  ts_ms: number;
  author: string;
  bot: boolean;
  text: string;
}

export type Split = "dev" | "test" | "hist" | "contrast";

export interface Win {
  name: string;
  channel: string;
  split: Split;
  kind: string;
  language: string;
  messages: Msg[];
  /** the primary labels */
  gold: Gold;
  /** the second, independent labelling (test windows) */
  gold2?: Gold;
  labeller: string;
  labeller2?: string;
}

interface LabelFile {
  window: string;
  labeller: string;
  labels: Record<string, string>;
  clusters: Record<string, string>;
}

/** Labels are keyed by the message's position in the labelling view; map them back to ids. */
function toGold(msgs: Msg[], f: LabelFile): Gold {
  const g: Gold = new Map();
  const authors = new Map<string, Set<string>>();
  msgs.forEach((m, n) => {
    const v = f.labels[String(n)];
    if (v === undefined) throw new Error(`${f.window}: no label for message ${n} (${f.labeller})`);
    g.set(m.id, v);
    (authors.get(v) ?? authors.set(v, new Set()).get(v)!).add(m.author);
  });
  // LABELING.md, "How labels are read": a cluster from fewer than two chatters is `x`
  for (const [id, v] of g) if (v !== "x" && v !== "unsure" && authors.get(v)!.size < 2) g.set(id, "x");
  return g;
}

export function splitFile(): { dev: string[]; test: string[] } {
  return JSON.parse(readFileSync(join(SEM, "split.json"), "utf8"));
}

/** Refuse to score against labels that changed after they were frozen. */
export function checkFrozen(): void {
  const lock = join(SEM, "labels.sha256");
  if (!existsSync(lock)) throw new Error("labels are not frozen (evals/semantic/labels.sha256 missing)");
  for (const line of readFileSync(lock, "utf8").split("\n").filter(Boolean)) {
    const [hash, file] = line.split(/\s+/);
    const got = createHash("sha256").update(readFileSync(join(SEM, file))).digest("hex");
    if (got !== hash) throw new Error(`${file} changed after the labels were frozen`);
  }
}

export function realWindows(): Win[] {
  const split = splitFile();
  const out: Win[] = [];
  for (const [s, names] of [["dev", split.dev], ["test", split.test]] as const) {
    for (const name of names) {
      const w = JSON.parse(readFileSync(join(SEM, "windows", `${name}.json`), "utf8"));
      const files = readdirSync(join(SEM, "labels")).filter((f) => f.startsWith(`${name}.`)).sort();
      if (!files.length) throw new Error(`${name}: not labelled`);
      const [a, b] = files.map((f) => JSON.parse(readFileSync(join(SEM, "labels", f), "utf8")) as LabelFile);
      out.push({
        name,
        channel: w.channel,
        split: s,
        kind: w.kind,
        language: w.language,
        messages: w.messages,
        gold: toGold(w.messages, a),
        labeller: a.labeller,
        ...(b ? { gold2: toGold(w.messages, b), labeller2: b.labeller } : {}),
      });
    }
  }
  return out;
}

/** The two windows of evals/grouping, scored as the historical experiment scored them. */
export function historicalWindows(): Win[] {
  const doc = JSON.parse(readFileSync(join(ROOT, "evals/grouping/pair_labels.json"), "utf8"));
  return doc.windows.map((w: { fixture: string; window: number; labels: { id: string; intent: string }[] }) => {
    const chat = new Map<string, { author: string; ts_ms: number; text: string }>();
    for (const line of readFileSync(join(ROOT, "evals/fixtures", w.fixture, "chat.jsonl"), "utf8").split("\n")) {
      if (line) {
        const r = JSON.parse(line);
        chat.set(r.id, r);
      }
    }
    const messages: Msg[] = w.labels.map((l) => {
      const r = chat.get(l.id)!;
      return { id: l.id, ts_ms: r.ts_ms, author: r.author, bot: false, text: r.text };
    });
    // `x<n>` ids are clusters of one in that file: the same thing as `x` here
    const gold: Gold = new Map(w.labels.map((l) => [l.id, /^x\d+$/.test(l.intent) ? "x" : l.intent]));
    const channel = w.fixture.split("_")[0];
    return {
      name: `${w.fixture} w${w.window}`,
      channel,
      split: "hist" as const,
      kind: "60s",
      language: "en",
      messages,
      gold,
      labeller: "evals/grouping (model-drafted)",
    };
  });
}

export function contrastWindows(): Win[] {
  const doc = JSON.parse(readFileSync(join(SEM, "contrast.json"), "utf8"));
  return doc.scenes.map((s: { name: string; messages: [string, string][] }, k: number) => {
    const messages: Msg[] = s.messages.map(([text], i) => ({
      id: `c${k}_${i}`,
      ts_ms: i * 1000,
      author: `a${i}`, // every line from a different chatter
      bot: false,
      text,
    }));
    return {
      name: `contrast: ${s.name}`,
      channel: doc.channel,
      split: "contrast" as const,
      kind: "constructed",
      language: "mixed",
      messages,
      gold: new Map(s.messages.map(([, c], i) => [`c${k}_${i}`, c])),
      labeller: "constructed",
    };
  });
}

/** Recorded text-embedding-3-small vectors of the historical windows (cache/llm), text -> vector. */
export function recordedOpenAI(): Map<string, Float32Array> {
  const out = new Map<string, Float32Array>();
  const dir = join(ROOT, "cache/llm");
  if (!existsSync(dir)) return out;
  for (const sub of readdirSync(dir)) {
    for (const f of readdirSync(join(dir, sub))) {
      const raw = readFileSync(join(dir, sub, f), "utf8");
      if (!raw.includes('"text-embedding-3-small"')) continue;
      const e = JSON.parse(raw);
      e.request.input.forEach((t: string, i: number) => out.set(t, Float32Array.from(e.response.data[i].embedding)));
    }
  }
  return out;
}
