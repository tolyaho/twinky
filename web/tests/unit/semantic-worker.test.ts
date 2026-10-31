// The worker itself, with the model replaced by a stub whose calls finish when the test says so.
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest";
import { MODEL, OPTIONS } from "../../src/semantic/config";
import type { FromWorker, ToWorker, WireItem } from "../../src/semantic/protocol";

const calls: { texts: string[]; done: () => void }[] = [];
let failNext = false;
vi.mock("@huggingface/transformers", () => ({
  env: {},
  pipeline: async () => async (texts: string[]) => {
    if (failNext) throw new Error("out of memory");
    if (texts[0] !== "warm up") await new Promise<void>((done) => calls.push({ texts, done }));
    // every text gets the same direction, so anything embedded can group
    return { dims: [texts.length, 2], data: new Float32Array(texts.flatMap(() => [1, 0])) };
  },
}));

const out: FromWorker[] = [];
const fakeSelf = { onmessage: null as null | ((e: MessageEvent<ToWorker>) => void), postMessage: (m: FromWorker) => out.push(m) };
const send = (m: ToWorker) => fakeSelf.onmessage!({ data: m } as MessageEvent<ToWorker>);
const tick = () => new Promise((r) => setTimeout(r, 0));
async function settle() {
  for (let i = 0; i < 20; i++) await tick();
}
async function finishAll() {
  for (let i = 0; i < 50; i++) {
    while (calls.length) calls.shift()!.done();
    await tick();
  }
}
const items = (prefix: string, k: number): WireItem[] =>
  Array.from({ length: k }, (_, i) => ({ key: `${prefix} ${i}`, weight: 1, authors: [`${prefix}${i}`] }));
const results = () => out.filter((m): m is Extract<FromWorker, { type: "result" }> => m.type === "result");

beforeAll(async () => {
  vi.stubGlobal("self", fakeSelf);
  await import("../../src/semantic/worker");
  send({ type: "init", spec: MODEL, device: "wasm" });
  await settle();
});
afterAll(() => vi.unstubAllGlobals());

describe("semantic worker", () => {
  it("loads, warms up and says it is ready", () => {
    expect(out[0]).toMatchObject({ type: "ready", device: "wasm" });
  });

  it("survives a channel switch while the model is busy, and answers only the new channel", async () => {
    send({ type: "reset", epoch: 1 });
    send({ type: "work", epoch: 1, seq: 1, items: items("one", 20), options: OPTIONS });
    await settle();
    expect(calls.length).toBe(1); // mid-embedding
    send({ type: "reset", epoch: 2 }); // the visitor opened another channel
    await finishAll();
    expect(out.some((m) => m.type === "failed")).toBe(false);
    expect(results().filter((r) => r.epoch === 1)).toEqual([]);

    send({ type: "work", epoch: 2, seq: 1, items: items("two", 3), options: OPTIONS });
    await finishAll();
    const r = results().at(-1)!;
    expect(r).toMatchObject({ epoch: 2, seq: 1, waiting: [] });
    expect(r.clusters[0].keys.sort()).toEqual(["two 0", "two 1", "two 2"]);
  });

  it("drops requests that were overtaken instead of queueing them", async () => {
    const before = results().length;
    send({ type: "work", epoch: 2, seq: 2, items: items("burst a", 5), options: OPTIONS });
    await settle();
    // while seq 2 is being embedded, three newer windows arrive: only the newest is answered next
    send({ type: "work", epoch: 2, seq: 3, items: items("burst b", 5), options: OPTIONS });
    send({ type: "work", epoch: 2, seq: 4, items: items("burst c", 5), options: OPTIONS });
    send({ type: "work", epoch: 2, seq: 5, items: items("burst d", 5), options: OPTIONS });
    await finishAll();
    expect(results().slice(before).map((r) => r.seq)).toEqual([2, 5]);
  });

  it("reports what it has not embedded yet while it catches up on a backlog", async () => {
    const before = results().length;
    send({ type: "work", epoch: 2, seq: 6, items: items("backlog", 120), options: OPTIONS });
    await finishAll();
    const mine = results().slice(before);
    expect(mine[0].waiting.length).toBeGreaterThan(0); // the first answer is partial, and says so
    expect(mine.at(-1)!.waiting).toEqual([]);
  });

  it("embeds a text once, however often it is sent", async () => {
    const seen = calls.length;
    send({ type: "work", epoch: 2, seq: 7, items: items("backlog", 120), options: OPTIONS });
    await settle();
    expect(calls.length).toBe(seen);
    expect(results().at(-1)!.seq).toBe(7);
  });

  it("reports a model failure instead of going quiet", async () => {
    failNext = true;
    send({ type: "work", epoch: 2, seq: 8, items: items("fresh", 2), options: OPTIONS });
    await settle();
    expect(out.at(-1)).toEqual({ type: "failed", reason: "out of memory" });
  });
});
