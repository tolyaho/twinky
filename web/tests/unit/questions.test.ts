import { beforeEach, describe, expect, it } from "vitest";
import { questions } from "../../src/cluster/pulse";
import type { ChatEvent } from "../../src/cluster/types";
import { lexicalGrouper } from "../../src/engine/session";
import { MODEL, OPTIONS } from "../../src/semantic/config";
import type { FromWorker, ToWorker } from "../../src/semantic/protocol";
import { SemanticGrouper, resetSharedWorker, type WorkerLike } from "../../src/semantic/live";
import { asksQuestion, questionsInChat } from "../../src/ui/asked";

const BASE = 1_700_000_000_000;
let n = 0;
const ev = (text: string, author: string, extra: Partial<ChatEvent> = {}): ChatEvent => ({
  id: `q${++n}`,
  ts_ms: BASE + n * 100,
  author,
  text,
  ...extra,
});
const byId = (es: ChatEvent[]) => new Map(es.map((e) => [e.id, e]));

describe("asksQuestion", () => {
  it("is a question with something in it", () => {
    expect(asksQuestion("what game is next?")).toBe(true);
    expect(asksQuestion("when are you switching games")).toBe(true);
    expect(asksQuestion("@someone is this live?")).toBe(true);
    expect(asksQuestion("is he playing ranked")).toBe(true);
  });

  it("is not an exclamation shaped like a question", () => {
    expect(asksQuestion("what a play")).toBe(false);
    expect(asksQuestion("WHAT THE HELL")).toBe(false);
    expect(asksQuestion("how lucky is that")).toBe(false);
    expect(asksQuestion("who cares?")).toBe(false);
    // asked, though: it ends with a question mark
    expect(asksQuestion("what a play?")).toBe(true);
  });

  it("is not a one-word reaction with a question mark", () => {
    for (const t of ["why?", "really?", "what?", "huh?", "??", "LUL"]) expect(asksQuestion(t), t).toBe(false);
  });
});

describe("questionsInChat, by wording (the word-rules board, or the model unavailable)", () => {
  beforeEach(() => {
    n = 0;
  });

  it("counts one question asked by several chatters once, with people apart from messages", () => {
    const es = [
      ev("what game is next?", "a"),
      ev("What game is next", "b"),
      ev("@streamer what game is NEXT??", "c"),
      ev("what game is next?", "a"), // the same person again
    ];
    const { repeated, others } = questionsInChat([], byId(es), false);
    expect(repeated).toHaveLength(1);
    expect(repeated[0]).toMatchObject({ askers: 3, how: "wording", groupKey: null });
    expect(repeated[0].event_ids).toHaveLength(4);
    expect(repeated[0].label).toBe("what game is next?");
    expect(others).toEqual([]);
  });

  it("does not present one person asking twenty times as the room asking", () => {
    const es = Array.from({ length: 20 }, () => ev("are you playing ranked tonight?", "spammer"));
    const { repeated, others } = questionsInChat([], byId(es), false);
    expect(repeated).toEqual([]);
    expect(others).toHaveLength(1);
    expect(others[0]).toMatchObject({ author: "spammer", times: 20 });
  });

  it("keeps different questions apart even when they share words", () => {
    const es = [
      ev("what game is next?", "a"),
      ev("what game is this?", "b"),
      ev("what game is this?", "c"),
    ];
    const { repeated, others } = questionsInChat([], byId(es), false);
    expect(repeated.map((q) => [q.label, q.askers])).toEqual([["what game is this?", 2]]);
    expect(others.map((o) => o.text)).toEqual(["what game is next?"]);
  });

  it("does not join questions that the word rules put in one shared-word group", () => {
    const es = [
      ev("is the boss hard?", "a"),
      ev("where is the boss?", "b"),
      ev("did he beat the boss?", "c"),
      ev("boss music slaps", "d"),
    ];
    const { groups } = lexicalGrouper.group(es);
    expect(groups.some((g) => g.rule === "token")).toBe(true); // "boss", three times
    const { repeated, others } = questionsInChat(groups, byId(es), false);
    expect(repeated).toEqual([]);
    expect(others).toHaveLength(3);
  });

  it("ranks by people, then by how recently it was asked, and leaves bots out", () => {
    const es = [
      ev("is this a rerun?", "a"),
      ev("is this a rerun?", "b"),
      ev("what rank is he?", "c"),
      ev("what rank is he?", "d"),
      ev("what rank is he?", "e"),
      ev("is this a rerun?", "nightbot", { bot: true }),
      ev("is this a rerun?", "f"),
      ev("how long is the stream?", "g"),
      ev("how long is the stream?", "h"),
    ];
    const { repeated } = questionsInChat([], byId(es), false);
    expect(repeated.map((q) => [q.label, q.askers])).toEqual([
      ["is this a rerun?", 3],
      ["what rank is he?", 3],
      ["how long is the stream?", 2],
    ]);
  });

  it("says nothing when nothing was asked", () => {
    const es = [ev("LUL", "a"), ev("gg", "b"), ev("what a play", "c")];
    expect(questionsInChat([], byId(es), false)).toEqual({ repeated: [], others: [] });
  });
});

describe("questionsInChat, by meaning", () => {
  beforeEach(() => {
    n = 0;
  });

  it("takes a question group as one question, counting only the messages that ask", () => {
    const es = [
      ev("what game is next?", "a"),
      ev("what are you playing after this?", "b"),
      ev("when are you switching games", "c"),
      ev("next game should be elden ring", "d"), // in the group, but not asking
    ];
    const group = { key: "t:t1", rule: "question", display: "what game is next?", event_ids: es.map((e) => e.id) };
    const { repeated } = questionsInChat([group], byId(es), true);
    expect(repeated).toHaveLength(1);
    expect(repeated[0]).toMatchObject({ key: "q:t:t1", askers: 3, how: "meaning", groupKey: "t:t1" });
    expect(repeated[0].event_ids).not.toContain(es[3].id);
  });

  it("does not make two different questions inside one topic one question", () => {
    const es = [
      ev("is this valorant", "a"),
      ev("what rank is he in valorant", "b"),
      ev("valorant is so back", "c"),
      ev("valorant again lets go", "d"),
      ev("valorant pog", "e"),
    ];
    const group = { key: "t:t2", rule: "topic", display: "valorant is so back", event_ids: es.map((e) => e.id) };
    const { repeated, others } = questionsInChat([group], byId(es), true);
    expect(repeated).toEqual([]);
    expect(others).toHaveLength(2);
  });

  it("joins the same wording inside a topic and opens that topic", () => {
    const es = [
      ev("his mic is muted", "a"),
      ev("we cant hear him", "b"),
      ev("is his mic muted?", "c"),
      ev("is his mic muted", "d"),
    ];
    const group = { key: "t:t3", rule: "topic", display: "his mic is muted", event_ids: es.map((e) => e.id) };
    const { repeated } = questionsInChat([group], byId(es), true);
    expect(repeated).toHaveLength(1);
    expect(repeated[0]).toMatchObject({ askers: 2, how: "wording", groupKey: "t:t3" });
  });
});

/** The page's grouper with a worker that answers from a fixed clustering. */
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
}

describe("paraphrased questions through the live grouper", () => {
  beforeEach(() => {
    resetSharedWorker();
    n = 0;
  });

  it("puts paraphrases the model clustered into one question, with its people", () => {
    const fake = new FakeWorker();
    const g = new SemanticGrouper("somechannel", MODEL, OPTIONS, () => fake);
    fake.emit({ type: "ready", device: "wasm", loadMs: 1 });
    const es = [
      ev("what game is next?", "a"),
      ev("what are you playing after this?", "b"),
      ev("when are you switching games", "c"),
      ev("what are you playing after this?", "b"), // one of them again
      ev("LUL", "d"),
      ev("KEKW", "e"),
    ];
    g.group(es);
    const work = fake.sent.filter((m): m is Extract<ToWorker, { type: "work" }> => m.type === "work").at(-1)!;
    fake.emit({
      type: "result",
      epoch: g.epoch,
      seq: work.seq,
      clusters: [{ keys: ["what game is next", "what are you playing after this", "when are you switching games"], coherence: 0.7 }],
      waiting: [],
      embedMs: 1,
      clusterMs: 1,
    });
    const { groups } = g.group(es);
    const q = groups.find((x) => x.rule === "question")!;
    expect(q).toBeDefined();
    const { repeated } = questionsInChat(groups, byId(es), true);
    expect(repeated).toHaveLength(1);
    expect(repeated[0]).toMatchObject({ askers: 3, how: "meaning", groupKey: q.key });
    expect(repeated[0].event_ids).toHaveLength(4);
  });
});

describe("the ported questions rule (pulse.ts) is unchanged", () => {
  it("still leaves two identical multi-word questions apart, as the Python rule does", () => {
    const rows = questions([
      ev("WHO DO YOU THINK WINS THE FINAL?", "a"),
      ev("who do you think wins the final", "b"),
      ev("what game is this?", "c"),
    ]);
    expect(rows.filter((r) => r.count === 1)).toHaveLength(3);
  });
});
