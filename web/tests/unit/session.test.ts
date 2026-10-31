import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  TwinkySession,
  liveSource,
  replaySource,
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
      FakeWebSocket.last().fireMessage(privmsgLine("LMAO", { id: `L${i}`, ts: BASE + i }));
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
});
