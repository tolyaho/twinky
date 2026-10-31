/// <reference lib="webworker" />
// The semantic worker: a small sentence-embedding model (Transformers.js, ONNX Runtime Web, CPU)
// and the grouping-by-meaning step, both off the main thread so chat and the board never wait on
// them. It keeps a bounded text -> vector cache, so a message repeated a thousand times is
// embedded once, and it always works on the newest request only: if chat outruns the model,
// stale requests are dropped rather than queued (backpressure), and the page is told how much is
// still waiting, so partial results are never presented as complete.
import { env, pipeline, type FeatureExtractionPipeline } from "@huggingface/transformers";
import { clusterItems, coherence, type Item } from "./cluster";
import type { FromWorker, ModelSpec, ToWorker } from "./protocol";

declare const self: DedicatedWorkerGlobalScope;

env.allowLocalModels = false; // weights come from the model hub (pinned revision), never this origin
env.useBrowserCache = true; // ... and are cached by the browser after the first visit

const BATCH = 48; // texts per model call: keeps one round well under a second on a slow CPU
const MAX_VECTORS = 6_000; // cache bound (~9 MB at 384 dims)
const POST_EVERY_MS = 700; // while catching up on a backlog, publish progress at most this often

let spec: ModelSpec | null = null;
let extractor: FeatureExtractionPipeline | null = null;
const vectors = new Map<string, Float32Array>(); // insertion order = recency (LRU)
let latest: Extract<ToWorker, { type: "work" }> | null = null;
let epoch = 0;
let running = false;

const post = (m: FromWorker) => self.postMessage(m);

self.onmessage = (e: MessageEvent<ToWorker>) => {
  const m = e.data;
  if (m.type === "init") {
    duty = Math.min(1, Math.max(0.1, m.duty ?? 1));
    void init(m.spec);
  }
  else if (m.type === "reset") {
    epoch = m.epoch;
    latest = null;
  } else if (m.type === "work" && m.epoch >= epoch) {
    epoch = m.epoch;
    latest = m; // replaces any request not yet started: only the newest window matters
    void pump();
  }
};

async function init(s: ModelSpec) {
  spec = s;
  // every file at the evaluated revision — `revision` alone leaves one config.json request on `main`
  env.remotePathTemplate = `{model}/resolve/${encodeURIComponent(s.revision)}/`;
  const t0 = performance.now();
  try {
    extractor = (await pipeline("feature-extraction", s.repo, {
      dtype: "q8",
      device: "wasm",
      revision: s.revision,
    })) as FeatureExtractionPipeline;
    await extractor(["warm up"], { pooling: s.pooling, normalize: true }); // first call compiles
    post({ type: "ready", device: "wasm", loadMs: Math.round(performance.now() - t0) });
    void pump();
  } catch (err) {
    post({ type: "failed", reason: err instanceof Error ? err.message : String(err) });
  }
}

const SUB = 16; // texts of similar length per model call: a batch is padded to its longest text
// Share of wall time the model may use while catching up: 1 = flat out. Below 1, the worker rests
// after each call so a phone's CPU (and the page that shares it) is never pegged.
let duty = 1;

async function embed(texts: string[]): Promise<void> {
  const sorted = [...texts].sort((a, b) => a.length - b.length);
  for (let i = 0; i < sorted.length; i += SUB) {
    const part = sorted.slice(i, i + SUB);
    const t0 = performance.now();
    const out = await extractor!(part.map((t) => (spec!.prefix ?? "") + t), { pooling: spec!.pooling, normalize: true });
    if (duty < 1) await new Promise((r) => setTimeout(r, ((performance.now() - t0) * (1 - duty)) / duty));
    const dim = out.dims[1];
    const data = out.data as Float32Array;
    part.forEach((t, r) => vectors.set(t, data.slice(r * dim, (r + 1) * dim)));
  }
  while (vectors.size > MAX_VECTORS) vectors.delete(vectors.keys().next().value as string);
}

async function pump() {
  if (running || !extractor) return;
  running = true;
  let lastPost = -Infinity;
  try {
    while (latest) {
      const w = latest;
      const missing = w.items.filter((i) => !vectors.has(i.key)); // the page sends them by priority
      const batch = missing.slice(0, BATCH).map((i) => i.key);
      let embedMs = 0;
      if (batch.length) {
        const t0 = performance.now();
        await embed(batch);
        embedMs = performance.now() - t0;
      }
      const waiting = missing.slice(batch.length).map((i) => i.key);
      if (!latest || latest.epoch !== w.epoch) continue; // the channel changed while the model ran
      if (waiting.length && latest === w && performance.now() - lastPost < POST_EVERY_MS) continue;

      const t1 = performance.now();
      const items: Item[] = [];
      for (const i of w.items) {
        const vec = vectors.get(i.key);
        if (!vec) continue;
        vectors.delete(i.key); // touch: recently used texts are evicted last
        vectors.set(i.key, vec);
        items.push({ key: i.key, vec, weight: i.weight, authors: new Set(i.authors) });
      }
      const clusters = clusterItems(items, w.options).map((g) => ({
        keys: g.map((i) => items[i].key),
        coherence: coherence(items, g),
      }));
      post({
        type: "result",
        epoch: w.epoch,
        seq: w.seq,
        clusters,
        waiting,
        embedMs: Math.round(embedMs),
        clusterMs: Math.round(performance.now() - t1),
      });
      lastPost = performance.now();
      if (latest === w && !waiting.length) latest = null;
      await new Promise((r) => setTimeout(r, 0)); // let newer requests arrive
    }
  } catch (err) {
    post({ type: "failed", reason: err instanceof Error ? err.message : String(err) });
    extractor = null;
  } finally {
    running = false;
  }
}
