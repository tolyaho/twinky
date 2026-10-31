import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TwitchChatClient, type IrcOptions, type IrcState } from "../../src/twitch/irc";
import type { ChatRow } from "../../src/twitch/parse";
import { FakeWebSocket, privmsgLine } from "./_fakews";

const WS = FakeWebSocket as unknown as typeof WebSocket;
const names366 = ":tmi.twitch.tv 366 justinfan1 #xqc :End of /NAMES list";

function makeClient(over: Partial<IrcOptions> = {}) {
  const rows: ChatRow[] = [];
  const states: { state: IrcState; attempt?: number }[] = [];
  const client = new TwitchChatClient({
    channel: "xqc",
    onRow: (r) => rows.push(r),
    onState: (state, info) => states.push({ state, attempt: info?.attempt }),
    WebSocketImpl: WS,
    quietAfterMs: 100,
    pingIntervalMs: 50,
    stallTimeoutMs: 200,
    baseBackoffMs: 1000,
    maxBackoffMs: 30000,
    ...over,
  });
  return { client, rows, states };
}

beforeEach(() => {
  vi.useFakeTimers();
  FakeWebSocket.reset();
});
afterEach(() => {
  vi.useRealTimers();
});

describe("TwitchChatClient lifecycle", () => {
  it("performs the anonymous handshake on open", () => {
    const { client } = makeClient();
    client.start();
    FakeWebSocket.last().fireOpen();
    const sent = FakeWebSocket.last().sent;
    expect(sent[0]).toBe("PASS SCHMOOPIIE");
    expect(sent[1]).toMatch(/^NICK justinfan\d+$/);
    expect(sent[2]).toBe("CAP REQ :twitch.tv/tags twitch.tv/commands");
    expect(sent[3]).toBe("JOIN #xqc");
    expect(client.state).toBe("connecting");
  });

  it("goes connected on 366, receiving on first message", () => {
    const { client, rows } = makeClient();
    client.start();
    FakeWebSocket.last().fireOpen();
    FakeWebSocket.last().fireMessage(names366);
    expect(client.state).toBe("connected");
    FakeWebSocket.last().fireMessage(privmsgLine("hello", { id: "a1" }));
    expect(client.state).toBe("receiving");
    expect(rows).toHaveLength(1);
    expect(rows[0]).toMatchObject({ id: "a1", text: "hello" });
  });

  it("dedupes repeated message ids", () => {
    const { rows, client } = makeClient();
    client.start();
    FakeWebSocket.last().fireOpen();
    const line = privmsgLine("same", { id: "dup1" });
    FakeWebSocket.last().fireMessage(line);
    FakeWebSocket.last().fireMessage(line);
    expect(rows).toHaveLength(1);
  });

  it("replies PONG to server PING", () => {
    const { client } = makeClient();
    client.start();
    FakeWebSocket.last().fireOpen();
    FakeWebSocket.last().sent.length = 0;
    FakeWebSocket.last().fireMessage("PING :tmi.twitch.tv");
    expect(FakeWebSocket.last().sent).toContain("PONG :tmi.twitch.tv");
  });

  it("goes quiet after silence, back to receiving on a message", () => {
    const { client } = makeClient();
    client.start();
    FakeWebSocket.last().fireOpen();
    FakeWebSocket.last().fireMessage(names366);
    vi.advanceTimersByTime(120);
    expect(client.state).toBe("quiet");
    FakeWebSocket.last().fireMessage(privmsgLine("back", { id: "b1" }));
    expect(client.state).toBe("receiving");
  });

  it("reconnects with backoff after an unexpected close", () => {
    const { client, states } = makeClient();
    client.start();
    FakeWebSocket.last().fireOpen();
    FakeWebSocket.last().fireMessage(names366);
    const before = FakeWebSocket.instances.length;
    FakeWebSocket.last().fireClose();
    expect(client.state).toBe("reconnecting");
    expect(states.some((s) => s.state === "reconnecting" && s.attempt === 1)).toBe(true);
    vi.advanceTimersByTime(1500); // past base backoff + jitter
    expect(FakeWebSocket.instances.length).toBe(before + 1);
    FakeWebSocket.last().fireOpen();
    expect(FakeWebSocket.last().sent).toContain("JOIN #xqc");
  });

  it("increments the backoff attempt across consecutive failures", () => {
    const { client, states } = makeClient();
    client.start();
    FakeWebSocket.last().fireOpen();
    FakeWebSocket.last().fireClose(); // attempt 1
    vi.advanceTimersByTime(1500);
    FakeWebSocket.last().fireClose(); // attempt 2 (never succeeded)
    const attempts = states.filter((s) => s.state === "reconnecting").map((s) => s.attempt);
    expect(attempts).toContain(1);
    expect(attempts).toContain(2);
  });

  it("forces a reconnect when inbound traffic stalls", () => {
    const { client } = makeClient();
    client.start();
    FakeWebSocket.last().fireOpen();
    FakeWebSocket.last().fireMessage(names366);
    const before = FakeWebSocket.instances.length;
    vi.advanceTimersByTime(260); // > stallTimeoutMs with no traffic
    vi.advanceTimersByTime(50); // let the 0-delay reconnect open a socket
    expect(FakeWebSocket.instances.length).toBeGreaterThan(before);
    expect(client.state).not.toBe("closed");
  });

  it("honours a server RECONNECT command", () => {
    const { client } = makeClient();
    client.start();
    FakeWebSocket.last().fireOpen();
    const before = FakeWebSocket.instances.length;
    FakeWebSocket.last().fireMessage(":tmi.twitch.tv RECONNECT");
    vi.advanceTimersByTime(50);
    expect(FakeWebSocket.instances.length).toBeGreaterThan(before);
  });

  it("stop() closes and never reconnects", () => {
    const { client } = makeClient();
    client.start();
    FakeWebSocket.last().fireOpen();
    FakeWebSocket.last().fireMessage(names366);
    const sock = FakeWebSocket.last();
    client.stop();
    expect(client.state).toBe("closed");
    const count = FakeWebSocket.instances.length;
    sock.fireClose(); // stray close from the torn-down socket
    vi.advanceTimersByTime(5000);
    expect(FakeWebSocket.instances.length).toBe(count); // no new socket
    expect(client.state).toBe("closed");
  });

  it("a stray close from an old socket does not drive the current one", () => {
    const { client } = makeClient();
    client.start();
    const first = FakeWebSocket.last();
    first.fireOpen();
    first.fireClose(); // triggers reconnect
    vi.advanceTimersByTime(1500);
    const second = FakeWebSocket.last();
    expect(second).not.toBe(first);
    const count = FakeWebSocket.instances.length;
    first.fireClose(); // old socket fires again — must be ignored
    vi.advanceTimersByTime(3000);
    expect(FakeWebSocket.instances.length).toBe(count);
  });

  it("requests the commands capability so a JOIN is acknowledged", () => {
    const { client } = makeClient();
    client.start();
    FakeWebSocket.last().fireOpen();
    expect(FakeWebSocket.last().sent).toContain("CAP REQ :twitch.tv/tags twitch.tv/commands");
  });

  it("treats ROOMSTATE as the join acknowledgement", () => {
    const { client } = makeClient();
    client.start();
    FakeWebSocket.last().fireOpen();
    FakeWebSocket.last().fireMessage("@emote-only=0;room-id=1 :tmi.twitch.tv ROOMSTATE #xqc");
    expect(client.state).toBe("connected");
  });

  it("reports not_found when Twitch never acknowledges the JOIN, and stops", () => {
    // stall watchdog well beyond the join timeout, as in production (150s vs 8s)
    const { client } = makeClient({ joinTimeoutMs: 500, stallTimeoutMs: 60_000 });
    client.start();
    FakeWebSocket.last().fireOpen();
    const count = FakeWebSocket.instances.length;
    vi.advanceTimersByTime(600);
    expect(client.state).toBe("not_found");
    vi.advanceTimersByTime(60_000);
    expect(FakeWebSocket.instances.length).toBe(count); // no reconnect loop
  });

  it("reconnects instead of not_found when a previously-joined channel stops acking", () => {
    const { client } = makeClient({ joinTimeoutMs: 500 });
    client.start();
    FakeWebSocket.last().fireOpen();
    FakeWebSocket.last().fireMessage(names366);
    FakeWebSocket.last().fireClose();
    vi.advanceTimersByTime(1500);
    FakeWebSocket.last().fireOpen(); // new socket, never acked
    vi.advanceTimersByTime(600);
    expect(client.state).not.toBe("not_found");
  });

  it("reports a suspended channel as not_found", () => {
    const { client } = makeClient();
    client.start();
    FakeWebSocket.last().fireOpen();
    FakeWebSocket.last().fireMessage(
      "@msg-id=msg_channel_suspended :tmi.twitch.tv NOTICE #xqc :This channel has been suspended.",
    );
    expect(client.state).toBe("not_found");
  });

  it("ignores non-chat commands such as USERNOTICE and CLEARCHAT", () => {
    const { client, rows } = makeClient();
    client.start();
    FakeWebSocket.last().fireOpen();
    FakeWebSocket.last().fireMessage(
      "@id=sub1;tmi-sent-ts=1700000000000;display-name=Sub :tmi.twitch.tv USERNOTICE #xqc :PRIVMSG-looking text",
    );
    FakeWebSocket.last().fireMessage(":tmi.twitch.tv CLEARCHAT #xqc :someone");
    expect(rows).toHaveLength(0);
  });
});
