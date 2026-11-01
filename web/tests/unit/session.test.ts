import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  MIN_CHATTERS,
  TwinkySession,
  liveSource,
  replaySource,
  streamClock,
  type ChatSource,
  type SourceState,
  type TickSnapshot,
} from "../../src/engine/session";
import type { ChatRow } from "../../src/twitch/parse";
import type { ChatEvent } from "../../src/cluster/types";
import { FakeWebSocket, privmsgLine } from "./_fakews";

const WS = FakeWebSocket as unknown as typeof WebSocket;
const BASE = 1_700_000_000_000;

function row(text: string, i: number, name = `n${i}`): ChatRow {
  return {
    id: `s${i}`,
    ts_ms: BASE + i,
    login: name,
    text,
    user_type: "",
    room_id: null,
    reply_to: null,
  };
}

function stub() {
  let onRow: (r: ChatRow) => void = () => {};
  let onState: (s: SourceState) => void = () => {};
  let stopped = false;
  const source: ChatSource = {
    start(r, s) {
      onRow = r;
      onState = s;
    },
    stop() {
      stopped = true;
    },
  };
  return {
    source,
    push: (r: ChatRow) => onRow(r),
    emit: (s: SourceState) => onState(s),
    get stopped() {
      return stopped;
    },
  };
}

function harness(source: ChatSource, over: Partial<ConstructorParameters<typeof TwinkySession>[0]> = {}) {
  const chats: ChatEvent[] = [];
  const ticks: TickSnapshot[] = [];
  const states: SourceState[] = [];
  const session = new TwinkySession({
    source,
    onChat: (e) => chats.push(e),
    onTick: (t) => ticks.push(t),
    onState: (s) => states.push(s),
    windowMs: 60_000,
    tickMs: 1_000,
    maxBuffer: 8_000,
    maxBufferMs: 120_000,
    ...over,
  });
  return { session, chats, ticks, states };
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(BASE);
  FakeWebSocket.reset();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("TwinkySession", () => {
  it("pseudonymises authors and counts messages", () => {
    const s = stub();
    const { session, chats, ticks } = harness(s.source);
    session.start();
    s.push(row("hello", 1, "RealLogin"));
    expect(chats).toHaveLength(1);
    expect(chats[0].author).toMatch(/^u_/);
    expect(chats[0].author).not.toContain("reallogin");
    vi.advanceTimersByTime(1000);
    expect(ticks.at(-1)?.messagesTotal).toBe(1);
  });

  it("clusters a reaction wave on tick", () => {
    const s = stub();
    const { session, ticks } = harness(s.source);
    session.start();
    for (let i = 0; i < 12; i++) s.push(row("LOL", i, `u${i}`));
    vi.advanceTimersByTime(1000);
    const groups = ticks.at(-1)!.groups;
    expect(groups.some((g) => g.rule === "reaction" && g.count === 12)).toBe(true);
  });

  it("fades old messages out of the trailing window", () => {
    const s = stub();
    const { session, ticks } = harness(s.source);
    session.start();
    for (let i = 0; i < 12; i++) s.push(row("LOL", i));
    vi.advanceTimersByTime(1000);
    expect(ticks.at(-1)!.windowMessages).toBe(12);
    vi.advanceTimersByTime(70_000); // advance past the 60s window with no new messages
    expect(ticks.at(-1)!.windowMessages).toBe(0);
    expect(ticks.at(-1)!.groups).toHaveLength(0);
  });

  it("bounds the buffer by count", () => {
    const s = stub();
    const { session, ticks } = harness(s.source, { maxBuffer: 10 });
    session.start();
    for (let i = 0; i < 50; i++) s.push(row("hi there friend", i, `u${i}`));
    vi.advanceTimersByTime(1000);
    expect(ticks.at(-1)!.messagesTotal).toBe(50);
    expect(ticks.at(-1)!.windowMessages).toBe(10); // only the last 10 retained
  });

  it("dedupes repeated ids defensively", () => {
    const s = stub();
    const { session, chats } = harness(s.source);
    session.start();
    s.push(row("dup", 1));
    s.push(row("dup", 1));
    expect(chats).toHaveLength(1);
  });

  it("stop() halts all callbacks (cancellation)", () => {
    const s = stub();
    const { session, chats, ticks } = harness(s.source);
    session.start();
    s.push(row("one", 1));
    session.stop();
    expect(s.stopped).toBe(true);
    const chatsAfter = chats.length;
    const ticksAfter = ticks.length;
    s.push(row("two", 2)); // stale event after stop
    vi.advanceTimersByTime(5000);
    expect(chats.length).toBe(chatsAfter);
    expect(ticks.length).toBe(ticksAfter);
  });

  it("does not leak a stopped session's data into a new one", () => {
    const a = stub();
    const ha = harness(a.source);
    ha.session.start();
    a.push(row("old channel chatter", 1));
    ha.session.stop();

    const b = stub();
    const hb = harness(b.source);
    hb.session.start();
    b.push(row("new channel chatter", 2));

    a.push(row("stale from old", 3)); // old source still emitting
    vi.advanceTimersByTime(1000);
    expect(hb.chats.map((c) => c.text)).toEqual(["new channel chatter"]);
    expect(hb.chats.some((c) => c.text.includes("old"))).toBe(false);
  });

  it("survives a high-volume burst with a bounded buffer", () => {
    const s = stub();
    const { session, ticks } = harness(s.source, { maxBuffer: 2000 });
    session.start();
    for (let i = 0; i < 3000; i++) s.push(row(i % 2 ? "LOL" : "W", i, `u${i % 400}`));
    vi.advanceTimersByTime(1000);
    expect(ticks.at(-1)!.messagesTotal).toBe(3000);
    expect(ticks.at(-1)!.windowMessages).toBeLessThanOrEqual(2000);
  });

  it("drives end-to-end from a live Twitch socket", () => {
    const source = liveSource("xqc", { WebSocketImpl: WS });
    const { session, chats, ticks, states } = harness(source);
    session.start();
    FakeWebSocket.last().fireOpen();
    FakeWebSocket.last().fireMessage(":tmi.twitch.tv 366 justinfan1 #xqc :End of /NAMES list");
    for (let i = 0; i < 5; i++) {
      FakeWebSocket.last().fireMessage(
        privmsgLine("LMAO", { id: `L${i}`, ts: BASE + i, name: `Viewer${i}` }),
      );
    }
    vi.advanceTimersByTime(1000);
    expect(chats).toHaveLength(5);
    expect(states).toContain("receiving");
    expect(ticks.at(-1)!.groups.some((g) => g.rule === "reaction")).toBe(true);
    session.stop();
  });

  it("replay source labels itself and never claims live", () => {
    const rows = Array.from({ length: 6 }, (_, i) => ({
      id: `r${i}`,
      ts_ms: BASE + i * 200,
      login: `u${i}`,
      text: "W",
    }));
    const source = replaySource(rows);
    const { session, chats, states } = harness(source);
    session.start();
    expect(states[0]).toBe("replay");
    vi.advanceTimersByTime(3000);
    expect(chats).toHaveLength(6);
    expect(states).toContain("ended");
    expect(states).not.toContain("receiving");
    session.stop();
  });

  it("a faster replay keeps the recording's own time: a minute on the board is a minute of chat", () => {
    // 120 messages, one a second: two minutes of recorded chat
    const rows = Array.from({ length: 120 }, (_, i) => ({ id: `r${i}`, ts_ms: 5_000 + i * 1_000, login: `u${i % 7}`, text: "W" }));
    const clock = streamClock(3);
    const source = replaySource(rows, { speed: 3, now: clock });
    const { session, chats, ticks } = harness(source, { now: clock });
    session.start();
    vi.advanceTimersByTime(30_000); // 30 s of wall time is 90 s of the recording
    expect(chats.length).toBe(91); // t = 0 s … 90 s of the recording
    // the spacing is the recording's, not a third of it
    expect(chats[1].ts_ms - chats[0].ts_ms).toBe(1_000);
    const last = ticks.at(-1)!;
    // a 60 s window holds 60 s of recorded chat (61 messages, one a second, ends inclusive), not 180 s
    expect(last.windowMessages).toBeGreaterThanOrEqual(60);
    expect(last.windowMessages).toBeLessThanOrEqual(61);
    expect(last.observedMs).toBe(60_000);
    // and the rate it implies is the recording's: about one message a second
    expect(Math.round((last.windowMessages / last.observedMs) * 60_000)).toBeLessThanOrEqual(61);
    session.stop();
  });

  it("counts distinct chatters per cluster", () => {
    const s = stub();
    const { session, ticks } = harness(s.source);
    session.start();
    // 10 LOLs from only 3 people
    for (let i = 0; i < 10; i++) s.push(row("LOL", i, `p${i % 3}`));
    vi.advanceTimersByTime(1000);
    const g = ticks.at(-1)!.groups.find((x) => x.rule === "reaction")!;
    expect(g.count).toBe(10);
    expect(g.chatters).toBe(3);
  });

  it("setWindow recounts immediately over the new span", () => {
    const s = stub();
    const { session, ticks } = harness(s.source, { windowMs: 60_000 });
    session.start();
    s.push(row("old", 1));
    vi.advanceTimersByTime(40_000);
    s.push({ ...row("new", 2), ts_ms: Date.now() });
    session.setWindow(30_000);
    expect(ticks.at(-1)!.windowMessages).toBe(1); // only the recent one is inside 30s
    session.setWindow(300_000);
    expect(ticks.at(-1)!.windowMessages).toBe(2);
  });

  it("flags the window as sampled when the count cap evicts in-window messages", () => {
    const s = stub();
    const { session, ticks } = harness(s.source, { maxBuffer: 10 });
    session.start();
    for (let i = 0; i < 5; i++) s.push(row("hi there", i, `u${i}`));
    vi.advanceTimersByTime(1000);
    expect(ticks.at(-1)!.sampled).toBe(false);
    for (let i = 5; i < 30; i++) s.push(row("hi there", i, `u${i}`));
    vi.advanceTimersByTime(1000);
    expect(ticks.at(-1)!.sampled).toBe(true);
  });
  it("does not show one chatter's repeats as an audience signal", () => {
    const s = stub();
    const { session, ticks } = harness(s.source);
    session.start();
    // one spammer: 6x LOL and 5x the same word — groups by the Python rules, but one person
    for (let i = 0; i < 6; i++) s.push(row("LOL", i, "spammer"));
    for (let i = 6; i < 11; i++) s.push(row("giveaway", i, "spammer"));
    // two real people laughing
    s.push(row("LMAO", 11, "alice"));
    s.push(row("KEKW", 12, "bob"));
    vi.advanceTimersByTime(1000);
    const t = ticks.at(-1)!;
    expect(MIN_CHATTERS).toBe(2);
    // the reaction wave survives (3 chatters), the one-person "giveaway" prefix group does not
    const reaction = t.groups.find((g) => g.rule === "reaction")!;
    expect(reaction.count).toBe(8);
    expect(reaction.chatters).toBe(3);
    expect(t.groups.some((g) => g.label.startsWith("give"))).toBe(false);
    expect(t.soloMessages).toBe(5);
    // the pulse agrees with the board: the dropped messages are ungrouped, not lost
    expect(t.pulse.active_groups).toBe(t.groups.length);
    expect(t.pulse.composition.singletons).toBe(t.windowMessages - 8);
  });

  it("labels a prefix group by its most common member, not a bare stem", () => {
    const s = stub();
    const { session, ticks } = harness(s.source);
    session.start();
    ["dracula", "dracula", "Dracula!!", "draconic", "dracarys"].forEach((t, i) =>
      s.push(row(t, i, `u${i}`)),
    );
    vi.advanceTimersByTime(1000);
    const g = ticks.at(-1)!.groups.find((x) => x.rule === "prefix")!;
    expect(g.label).toBe("drac…"); // the Python label is untouched
    expect(g.display).toBe("dracula");
  });

  it("exposes every grouped message as evidence", () => {
    const s = stub();
    const { session, ticks } = harness(s.source);
    session.start();
    for (let i = 0; i < 7; i++) s.push(row("LOL", i, `u${i}`));
    vi.advanceTimersByTime(1000);
    const t = ticks.at(-1)!;
    for (const g of t.groups) {
      for (const id of g.event_ids) expect(t.events.get(id)?.id).toBe(id);
    }
  });

  it("divides rates by the time actually observed while the window warms up", () => {
    const s = stub();
    const { session, ticks } = harness(s.source, { windowMs: 60_000, maxBufferMs: 120_000 });
    session.start();
    vi.advanceTimersByTime(20_000);
    let t = ticks.at(-1)!;
    expect(t.warm).toBe(false);
    expect(t.observedMs).toBeGreaterThanOrEqual(19_000);
    expect(t.observedMs).toBeLessThanOrEqual(21_000);
    vi.advanceTimersByTime(60_000);
    t = ticks.at(-1)!;
    expect(t.warm).toBe(true);
    expect(t.observedMs).toBe(60_000);
  });
});
