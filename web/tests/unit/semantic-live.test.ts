import { beforeEach, describe, expect, it } from "vitest";
import type { ChatEvent } from "../../src/cluster/types";
import { clusterItems, coherence, type Item } from "../../src/semantic/cluster";
import { MODEL, OPTIONS } from "../../src/semantic/config";
import { hybridGroups, prepAll } from "../../src/semantic/hybrid";
import type { FromWorker, ToWorker } from "../../src/semantic/protocol";
import {
  MAX_ITEMS,
  SemanticGrouper,
  resetSharedWorker,
  sameWordVariants,
  type WorkerLike,
} from "../../src/semantic/live";

/** A worker that records what the page sends and answers only when the test says so. */
class FakeWorker implements WorkerLike {
  sent: ToWorker[] = [];
  onmessage: ((e: MessageEvent<FromWorker>) => void) | null = null;
  onerror: ((e: ErrorEvent) => void) | null = null;
  postMessage(m: ToWorker) {
    this.sent.push(m);
  }
  emit(m: FromWorker) {
    this.onmessage?.({ data: m } as MessageEvent<FromWorker>);
  }
  work() {
    return this.sent.filter((m): m is Extract<ToWorker, { type: "work" }> => m.type === "work");
  }
  lastWork() {
    return this.work().at(-1)!;
  }
}

const BASE = 1_700_000_000_000;
let n = 0;
const ev = (text: string, author: string): ChatEvent => ({ id: `m${++n}`, ts_ms: BASE + n, author, text });

let fake: FakeWorker;
let made = 0;
const make = () => {
  made++;
  return fake;
};
const grouper = (channel = "somechannel") => new SemanticGrouper(channel, MODEL, OPTIONS, make);

/** The worker's answer for the newest request: these texts are one cluster each group. */
function answer(g: SemanticGrouper, clusters: string[][], waiting: string[] = []) {
  const w = fake.lastWork();
  fake.emit({
    type: "result",
    epoch: g.epoch,
    seq: w.seq,
    clusters: clusters.map((keys) => ({ keys, coherence: 0.8 })),
    waiting,
    embedMs: 1,
    clusterMs: 1,
  });
}

const MUTED = ["his mic is muted", "we cant hear him", "no audio"];
const chat = () => [
  ev("his mic is muted", "a"),
  ev("we cant hear him", "b"),
  ev("no audio", "c"),
  ev("LUL", "d"),
  ev("KEKW", "e"),
  ev("what game is this", "f"),
];

beforeEach(() => {
  resetSharedWorker();
  fake = new FakeWorker();
  made = 0;
});

describe("SemanticGrouper", () => {
  it("groups reactions at once and counts every text message as unread while the model loads", () => {
    const g = grouper();
    const r = g.group(chat());
    expect(r.semantic.state).toBe("loading");
    expect(r.groups.map((x) => [x.rule, x.count])).toEqual([["reaction", 2]]);
    expect(r.semantic.textMessages).toBe(4);
    expect(r.semantic.pending).toBe(4);
  });

  it("shows the same words from several chatters at once, without waiting for the model", () => {
    const g = grouper();
    const r = g.group([ev("clip it", "a"), ev("clip it", "b"), ev("his mic is muted", "c")]);
    expect(r.semantic.state).toBe("loading");
    expect(r.groups.map((x) => [x.rule, x.label, x.count])).toEqual([["phrase", "clip it", 2]]);
    expect(r.semantic.pending).toBe(3); // shown, but not read by the model: still counted as unread
  });

  it("shows a topic once the model has answered for this window, and nothing is left unread", () => {
    const g = grouper();
    const window = chat();
    g.group(window);
    fake.emit({ type: "ready", device: "wasm", loadMs: 900 });
    answer(g, [MUTED]);
    const r = g.group(window);
    const topic = r.groups.find((x) => x.rule === "topic")!;
    expect(topic.count).toBe(3);
    expect(topic.chatters).toBe(3);
    expect(topic.samples.length).toBeGreaterThan(0);
    expect(topic.samples).not.toContain(topic.label); // a sample is another wording
    expect(r.semantic).toMatchObject({ state: "ready", pending: 0, loadMs: 900 });
  });

  it("counts texts the worker has not embedded yet as unread", () => {
    const g = grouper();
    const window = chat();
    g.group(window);
    fake.emit({ type: "ready", device: "wasm", loadMs: 1 });
    answer(g, [], ["no audio", "what game is this"]);
    expect(g.group(window).semantic.pending).toBe(2);
  });

  it("counts messages that arrived after the last answer as unread", () => {
    const g = grouper();
    const window = chat();
    g.group(window);
    fake.emit({ type: "ready", device: "wasm", loadMs: 1 });
    answer(g, [MUTED]);
    const r = g.group([...window, ev("is this ranked", "g")]);
    expect(r.semantic.pending).toBe(1);
  });

  it("sends the window once per change, not on every recount", () => {
    const g = grouper();
    const window = chat();
    g.group(window);
    g.group(window);
    expect(fake.work()).toHaveLength(1);
    g.group([...window, ev("hello", "h")]);
    expect(fake.work()).toHaveLength(2);
  });

  it("never hands the model more than MAX_ITEMS texts, repeated ones first", () => {
    const g = grouper();
    const window: ChatEvent[] = [];
    for (let i = 0; i < MAX_ITEMS + 100; i++) window.push(ev(`distinct message number ${i}`, `u${i}`));
    window.push(ev("the same words again", "x1"), ev("the same words again", "x2"));
    g.group(window);
    const items = fake.lastWork().items;
    expect(items).toHaveLength(MAX_ITEMS);
    expect(items[0]).toMatchObject({ key: "the same words again", weight: 2 });
  });

  it("shares one worker across channels and ignores an earlier channel's late answer", () => {
    const first = grouper("one");
    first.group(chat());
    const staleSeq = fake.lastWork().seq;
    first.stop();
    const second = grouper("two");
    expect(made).toBe(1);
    expect(fake.sent.filter((m) => m.type === "init")).toHaveLength(1);
    expect(fake.sent.at(-1)).toEqual({ type: "reset", epoch: second.epoch });
    expect(second.epoch).toBeGreaterThan(first.epoch);

    fake.emit({ type: "ready", device: "wasm", loadMs: 1 });
    const window = chat();
    second.group(window);
    // the first channel's answer arrives late: it must not become the second channel's topics
    fake.emit({ type: "result", epoch: first.epoch, seq: staleSeq, clusters: [{ keys: MUTED, coherence: 1 }], waiting: [], embedMs: 1, clusterMs: 1 });
    const r = second.group(window);
    expect(r.groups.some((x) => x.rule === "topic")).toBe(false);
    expect(r.semantic.pending).toBe(4);
  });

  it("knows the model is ready when it joins after the model loaded", () => {
    grouper("one").group(chat());
    fake.emit({ type: "ready", device: "wasm", loadMs: 5 });
    expect(grouper("two").state).toBe("ready");
  });

  it("keeps a topic's id and label while its members change", () => {
    const g = grouper();
    const window = chat();
    g.group(window);
    fake.emit({ type: "ready", device: "wasm", loadMs: 1 });
    answer(g, [MUTED]);
    const before = g.group(window).groups.find((x) => x.rule === "topic")!;

    const more = [...window, ev("audio is gone", "i"), ev("no audio", "j")];
    g.group(more);
    answer(g, [[...MUTED, "audio is gone"]]);
    const after = g.group(more).groups.find((x) => x.rule === "topic")!;
    expect(after.key).toBe(before.key);
    expect(after.count).toBe(5);
    // "no audio" now has 2 messages against the old label's 1: it clearly outweighs it and takes over
    expect(after.label).toBe("no audio");
  });

  it("does not let a near-tie take the label", () => {
    const g = grouper();
    const window = [ev("his mic is muted", "a"), ev("his mic is muted", "b"), ev("we cant hear him", "c")];
    g.group(window);
    fake.emit({ type: "ready", device: "wasm", loadMs: 1 });
    answer(g, [["his mic is muted", "we cant hear him"]]);
    expect(g.group(window).groups[0].label).toBe("his mic is muted");
    const more = [...window, ev("we cant hear him", "d"), ev("we cant hear him", "e")];
    g.group(more);
    answer(g, [["we cant hear him", "his mic is muted"]]);
    // 3 against 2 is exactly 1.5x: the old label goes
    expect(g.group(more).groups[0].label).toBe("we cant hear him");
    const tie = [...more, ev("his mic is muted", "f")];
    g.group(tie);
    answer(g, [["we cant hear him", "his mic is muted"]]);
    // 3 against 3 now: the label stays where it is
    expect(g.group(tie).groups[0].label).toBe("we cant hear him");
  });

  it("marks a group of questions as a question", () => {
    const g = grouper();
    const window = [ev("what game is this", "a"), ev("which game is it?", "b"), ev("whats this game called", "c")];
    g.group(window);
    fake.emit({ type: "ready", device: "wasm", loadMs: 1 });
    answer(g, [["what game is this", "which game is it?", "whats this game called"]]);
    expect(g.group(window).groups[0].rule).toBe("question");
  });

  it("calls one word in several spellings repeated, not a topic", () => {
    const g = grouper();
    const window = [ev("amethyst", "a"), ev("Amethysts", "b"), ev("amethyst", "c")];
    g.group(window);
    fake.emit({ type: "ready", device: "wasm", loadMs: 1 });
    answer(g, [["amethyst", "amethysts"]]);
    expect(g.group(window).groups[0].rule).toBe("phrase");
  });

  it("falls back to the word rules, and says so, when the model cannot run", () => {
    const g = grouper();
    const window = [
      ev("the boss fight is so hard", "a"),
      ev("boss is unbeatable", "b"),
      ev("that boss though", "c"),
    ];
    g.group(window);
    fake.emit({ type: "failed", reason: "no WebAssembly" });
    const r = g.group(window);
    expect(r.semantic).toMatchObject({ state: "failed", reason: "no WebAssembly", pending: 0 });
    expect(r.groups.map((x) => x.rule)).toEqual(["token"]);
  });

  it("treats a crashed worker as a failed model", () => {
    const g = grouper();
    fake.onerror?.({ message: "" } as ErrorEvent);
    expect(g.state).toBe("failed");
  });

  it("does not count one chatter repeating themselves as the room", () => {
    const g = grouper();
    const r = g.group([ev("first", "a"), ev("first", "a"), ev("first", "a")]);
    expect(r.groups).toEqual([]);
    expect(r.soloMessages).toBe(3);
  });
});

describe("parity with the evaluated pipeline", () => {
  it("once the model has read everything, the board holds exactly hybridGroups' groups", () => {
    // toy vectors: texts about audio point one way, about the game another, the rest elsewhere
    const vec = (t: string) =>
      new Float32Array(/mic|hear|audio|sound/.test(t) ? [1, 0, 0] : /game|playing/.test(t) ? [0, 1, 0] : [0, 0, 1]);
    const window = [
      ev("his mic is muted", "a"), ev("we cant hear him", "b"), ev("no audio", "c"), ev("sound is gone", "d"),
      ev("what game is this", "e"), ev("which game is he playing", "f"), ev("clip it", "g"), ev("clip it", "h"),
      ev("LUL", "i"), ev("KEKW", "j"), ev("ok", "k"), ev("first", "l"),
    ];
    const g = grouper("somechannel");
    g.group(window);
    fake.emit({ type: "ready", device: "wasm", loadMs: 1 });
    const w = fake.lastWork();
    const items: Item[] = w.items.map((i) => ({ key: i.key, vec: vec(i.key), weight: i.weight, authors: new Set(i.authors) }));
    const clusters = clusterItems(items, w.options).map((c) => ({ keys: c.map((i) => items[i].key), coherence: coherence(items, c) }));
    fake.emit({ type: "result", epoch: g.epoch, seq: w.seq, clusters, waiting: [], embedMs: 0, clusterMs: 0 });
    const board = g.group(window);
    const evaluated = hybridGroups(prepAll(window, "somechannel"), vec, OPTIONS);
    const asSets = (gs: { ids?: string[]; event_ids?: string[] }[]) =>
      gs.map((x) => [...(x.ids ?? x.event_ids!)].sort().join(",")).sort();
    expect(asSets(board.groups)).toEqual(asSets(evaluated.groups));
    expect(board.groups.length).toBeGreaterThanOrEqual(3);
    expect(board.semantic.pending).toBe(0);
  });
});

describe("sameWordVariants", () => {
  it("is one word in several spellings", () => {
    expect(sameWordVariants(["amethyst", "amethysts", "Amethyst".toLowerCase()])).toBe(true);
    expect(sameWordVariants(["drivers", "driving"])).toBe(true);
  });
  it("is not different words, phrases, or very short words", () => {
    expect(sameWordVariants(["america", "dragon"])).toBe(false);
    expect(sameWordVariants(["his mic", "his mic is muted"])).toBe(false);
    expect(sameWordVariants(["gg"])).toBe(false);
    expect(sameWordVariants(["abc", "abcd"])).toBe(false);
  });
});
