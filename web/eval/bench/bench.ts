// In-page half of the browser benchmark: drives the real semantic worker (src/semantic/worker.ts)
// and measures what a visitor would experience — model load, embedding throughput, and whether
// the main thread stays responsive while the worker is busy.
import type { FromWorker, ModelSpec, ToWorker } from "../../src/semantic/protocol";

interface BenchResult {
  loadMs: number;
  device: string;
  texts: number;
  embedMs: number;
  perText: number;
  rounds: number;
  clusterMsMax: number;
  maxFrameGapMs: number;
  idleGapMs: number;
  frames: number;
  heapMB: number | null;
  uaMemoryMB: number | null;
  webgpu: boolean;
  crossOriginIsolated: boolean;
  hardwareConcurrency: number;
}

declare global {
  interface Window {
    bench: (spec: ModelSpec, texts: string[]) => Promise<BenchResult>;
  }
}

window.bench = async (spec, texts) => {
  const duty = Number(new URLSearchParams(location.search).get("duty") ?? "1");
  const worker = new Worker(new URL("../../src/semantic/worker.ts", import.meta.url), { type: "module" });
  const send = (m: ToWorker) => worker.postMessage(m);
  const next = <T extends FromWorker["type"]>(type: T) =>
    new Promise<Extract<FromWorker, { type: T }>>((resolve, reject) => {
      const h = (e: MessageEvent<FromWorker>) => {
        if (e.data.type === "failed") reject(new Error(e.data.reason));
        if (e.data.type === type) {
          worker.removeEventListener("message", h);
          resolve(e.data as Extract<FromWorker, { type: T }>);
        }
      };
      worker.addEventListener("message", h);
    });

  // baseline: the longest frame gap over two idle seconds, before any model work
  const idleGapMs = await new Promise<number>((resolve) => {
    let prev = performance.now(), gap = 0;
    const end = prev + 2_000;
    const f = () => {
      const now = performance.now();
      gap = Math.max(gap, now - prev);
      prev = now;
      if (now < end) requestAnimationFrame(f);
      else resolve(Math.round(gap));
    };
    requestAnimationFrame(f);
  });

  send({ type: "init", spec, device: "wasm", duty });
  const ready = await next("ready");

  // main-thread responsiveness while the worker embeds: the longest gap between animation frames
  let frames = 0, last = performance.now(), maxGap = 0, run = true;
  const tick = () => {
    const now = performance.now();
    maxGap = Math.max(maxGap, now - last);
    last = now;
    frames++;
    if (run) requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);

  const t0 = performance.now();
  const items = texts.map((key) => ({ key, weight: 1, authors: [key] }));
  send({ type: "work", epoch: 1, seq: 1, items, options: { method: "center", threshold: 0.95, minMessages: 2, minAuthors: 2, refine: 2 } });
  let rounds = 0, clusterMsMax = 0;
  for (;;) {
    const r = await next("result");
    rounds++;
    clusterMsMax = Math.max(clusterMsMax, r.clusterMs);
    if (!r.waiting.length) break;
  }
  const embedMs = performance.now() - t0;
  run = false;
  // per-context memory, worker included (Chromium, cross-origin isolated pages only)
  let uaMemoryMB: number | null = null;
  const mua = (performance as unknown as { measureUserAgentSpecificMemory?: () => Promise<{ bytes: number }> })
    .measureUserAgentSpecificMemory;
  try {
    if (self.crossOriginIsolated && mua) uaMemoryMB = Math.round((await mua.call(performance)).bytes / 1e6);
  } catch {
    uaMemoryMB = null; // needs COEP require-corp; the page is served credentialless
  }
  worker.terminate();
  const mem = (performance as unknown as { memory?: { usedJSHeapSize: number } }).memory;
  return {
    loadMs: ready.loadMs,
    device: ready.device,
    texts: texts.length,
    embedMs: Math.round(embedMs),
    perText: +(embedMs / texts.length).toFixed(2),
    rounds,
    clusterMsMax,
    maxFrameGapMs: Math.round(maxGap),
    idleGapMs,
    frames,
    heapMB: mem ? Math.round(mem.usedJSHeapSize / 1e6) : null,
    uaMemoryMB,
    webgpu: "gpu" in navigator,
    crossOriginIsolated: self.crossOriginIsolated,
    hardwareConcurrency: navigator.hardwareConcurrency,
  };
};
