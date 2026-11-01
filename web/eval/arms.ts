// The arms compared on the same windows. Each returns a prediction (message id -> group, or null).
//   A  lexical   the shipped grouping: groupChat + MIN_CHATTERS, exactly as the live board runs it
//   B  embed     embeddings only: every message's raw text embedded, grouped by meaning
//   C  hybrid    deterministic fast path for reactions/repeats + grouping by meaning for the rest
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { groupChat } from "../src/cluster/group";
import { MIN_CHATTERS } from "../src/engine/session";
import { clusterItems, type ClusterOptions, type Item } from "../src/semantic/cluster";
import { hybridGroups, prepAll, textsToEmbed, type HybridOptions } from "../src/semantic/hybrid";
import type { Msg, Win } from "./data";
import { load, type Candidate, type Embedder } from "./embedders";
import type { Pred } from "./score";

export function armLexical(w: Win): Pred {
  const pred: Pred = new Map(w.messages.map((m) => [m.id, null]));
  const author = new Map(w.messages.map((m) => [m.id, m.author]));
  for (const g of groupChat(w.messages)) {
    if (new Set(g.event_ids.map((id) => author.get(id))).size < MIN_CHATTERS) continue;
    for (const id of g.event_ids) pred.set(id, g.key);
  }
  return pred;
}

const unit = (v: Float32Array) => {
  let n = 0;
  for (const x of v) n += x * x;
  n = Math.sqrt(n) || 1;
  return v.map((x) => x / n);
};

/** B: no fast path at all — the raw text of every message, bots and links included. */
export function armEmbed(w: Win, vectorOf: (t: string) => Float32Array | undefined, o: ClusterOptions): Pred {
  const pred: Pred = new Map(w.messages.map((m) => [m.id, null]));
  const items: (Item & { ids: string[] })[] = [];
  const index = new Map<string, number>();
  for (const m of w.messages) {
    const v = vectorOf(m.text);
    if (!v) throw new Error(`no vector for ${JSON.stringify(m.text)}`);
    let i = index.get(m.text);
    if (i === undefined) {
      i = items.length;
      index.set(m.text, i);
      items.push({ key: m.text, vec: unit(v), weight: 0, authors: new Set(), ids: [] });
    }
    items[i].weight++;
    (items[i].authors as Set<string>).add(m.author);
    items[i].ids.push(m.id);
  }
  clusterItems(items, o).forEach((g, k) => g.forEach((i) => items[i].ids.forEach((id) => pred.set(id, `b${k}`))));
  return pred;
}

export function armHybrid(w: Win, vectorOf: (t: string) => Float32Array | undefined, o: HybridOptions): Pred {
  const pred: Pred = new Map(w.messages.map((m) => [m.id, null]));
  const r = hybridGroups(prepAll(w.messages, w.channel, o), vectorOf, o);
  if (r.pending) throw new Error(`${w.name}: ${r.pending} texts without a vector`);
  for (const g of r.groups) for (const id of g.ids) pred.set(id, g.key);
  return pred;
}

export function hybridTexts(w: Win, o: HybridOptions = {}): string[] {
  return textsToEmbed(prepAll(w.messages, w.channel, o)); // every text: the store serves all models
}

// --- vectors, cached on disk per model so sweeps never re-encode ------------------------------
const CACHE = fileURLToPath(new URL("./.cache/", import.meta.url));

export class VectorStore {
  private mem = new Map<string, Float32Array>();
  private dirty = false;
  private embedder?: Embedder;
  constructor(readonly c: Candidate) {
    const f = this.file();
    if (existsSync(f)) {
      const raw: Record<string, string> = JSON.parse(readFileSync(f, "utf8"));
      for (const [t, b64] of Object.entries(raw)) {
        const buf = Buffer.from(b64, "base64");
        this.mem.set(t, new Float32Array(buf.buffer, buf.byteOffset, buf.byteLength / 4));
      }
    }
  }
  private file() {
    return join(CACHE, `${this.c.key}.json`);
  }
  get = (t: string) => this.mem.get(t);
  async ensure(texts: string[]): Promise<void> {
    const missing = [...new Set(texts)].filter((t) => !this.mem.has(t));
    if (!missing.length) return;
    this.embedder ??= await load(this.c);
    const vecs = await this.embedder.embed(missing);
    missing.forEach((t, i) => this.mem.set(t, vecs[i]));
    this.dirty = true;
  }
  save(): void {
    if (!this.dirty) return;
    mkdirSync(CACHE, { recursive: true });
    const out: Record<string, string> = {};
    for (const [t, v] of this.mem) out[t] = Buffer.from(v.buffer, v.byteOffset, v.byteLength).toString("base64");
    writeFileSync(this.file(), JSON.stringify(out));
    this.dirty = false;
  }
}

export type { Msg };
