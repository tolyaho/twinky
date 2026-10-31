// The session engine: it turns a stream of raw chat rows into a continuously updating clustering
// view, over a trailing time window, with bounded memory. It is deliberately source-agnostic —
// a live Twitch socket and a recorded replay drive it through the same `ChatSource` seam, so the
// clustering path is identical and a replay can never be mistaken for live by accident (the source
// decides the status it reports, and replay reports "replay").
import { groupChat } from "../cluster/group";
import { pulse, type Pulse } from "../cluster/pulse";
import type { ChatEvent, Group } from "../cluster/types";
import { TwitchChatClient, type IrcState } from "../twitch/irc";
import type { ChatRow } from "../twitch/parse";
import { Pseudonymizer } from "./pseudonym";

export type SourceState =
  | IrcState
  | "replay" // a recorded capture, always labelled as such
  | "ended"; // replay finished

export interface ChatSource {
  start(onRow: (row: ChatRow) => void, onState: (s: SourceState, info?: SourceInfo) => void): void;
  stop(): void;
}

export interface SourceInfo {
  message?: string;
  attempt?: number;
}

/** A group plus what the browser can add on top of the Python rules: distinct authors. */
export interface LiveGroup extends Group {
  chatters: number;
}

export interface TickSnapshot {
  windowMs: [number, number];
  groups: LiveGroup[];
  /** True when the count cap evicted messages that were still inside the window. */
  sampled: boolean;
  pulse: Pulse;
  messagesTotal: number;
  windowMessages: number;
  serverNow: number;
}

export interface SessionOptions {
  source: ChatSource;
  onChat: (event: ChatEvent) => void;
  onTick: (snap: TickSnapshot) => void;
  onState: (s: SourceState, info?: SourceInfo) => void;
  windowMs?: number; // trailing analysis window (default 60s)
  tickMs?: number; // how often clusters recount (default 1500ms)
  maxBufferMs?: number; // how far back events are retained (default 330s: room for a 5m window)
  maxBuffer?: number; // hard cap on retained events (default 20000)
  pseudonymizer?: Pseudonymizer;
  now?: () => number;
}

export class TwinkySession {
  private readonly o: Required<Omit<SessionOptions, "pseudonymizer">> & {
    pseudonymizer: Pseudonymizer;
  };
  private readonly buffer: ChatEvent[] = [];
  private readonly firstSeen = new Map<string, number>(); // author -> first ts in session
  private readonly ids = new Set<string>();
  private clockOffset = 0; // serverTs - localNow, so we can advance the window in real time
  private haveOffset = false;
  private messagesTotal = 0;
  private evictedUntil = -Infinity; // newest ts dropped by the count cap
  private tickTimer?: ReturnType<typeof setInterval>;
  private stopped = false;

  constructor(opts: SessionOptions) {
    this.o = {
      source: opts.source,
      onChat: opts.onChat,
      onTick: opts.onTick,
      onState: opts.onState,
      windowMs: opts.windowMs ?? 60_000,
      tickMs: opts.tickMs ?? 1_500,
      maxBufferMs: opts.maxBufferMs ?? 330_000,
      maxBuffer: opts.maxBuffer ?? 20_000,
      now: opts.now ?? (() => Date.now()),
      pseudonymizer: opts.pseudonymizer ?? new Pseudonymizer(),
    };
  }

  start(): void {
    this.stopped = false;
    this.o.source.start(
      (row) => this.ingest(row),
      (s, info) => {
        if (!this.stopped) this.o.onState(s, info);
      },
    );
    this.tickTimer = setInterval(() => this.tick(), this.o.tickMs);
  }

  /** Change the trailing window and recount immediately. Capped by what the buffer retains. */
  setWindow(ms: number): void {
    this.o.windowMs = Math.min(ms, this.o.maxBufferMs);
    this.tick();
  }

  /** Cancellation: after stop() no further chat, tick or state callbacks fire for this session. */
  stop(): void {
    this.stopped = true;
    if (this.tickTimer !== undefined) clearInterval(this.tickTimer);
    this.tickTimer = undefined;
    this.o.source.stop();
  }

  private serverNow(): number {
    return this.haveOffset ? this.o.now() + this.clockOffset : this.o.now();
  }

  private ingest(row: ChatRow): void {
    if (this.stopped) return;
    if (!row.id || this.ids.has(row.id)) return; // dedupe is also enforced here, defensively
    this.ids.add(row.id);

    this.clockOffset = row.ts_ms - this.o.now();
    this.haveOffset = true;

    const event: ChatEvent = {
      id: row.id,
      ts_ms: row.ts_ms,
      author: this.o.pseudonymizer.label(row.login),
      text: row.text,
    };
    if (!this.firstSeen.has(event.author)) this.firstSeen.set(event.author, event.ts_ms);
    this.buffer.push(event);
    this.messagesTotal += 1;
    this.prune();
    this.o.onChat(event);
  }

  private prune(): void {
    // Bound by both age and count so a busy channel cannot grow memory without limit.
    const floor = this.serverNow() - this.o.maxBufferMs;
    let drop = 0;
    while (drop < this.buffer.length && this.buffer[drop].ts_ms < floor) drop++;
    if (this.buffer.length - drop > this.o.maxBuffer) {
      drop = this.buffer.length - this.o.maxBuffer;
      this.evictedUntil = Math.max(this.evictedUntil, this.buffer[drop - 1].ts_ms);
    }
    if (drop > 0) {
      for (let i = 0; i < drop; i++) this.ids.delete(this.buffer[i].id);
      this.buffer.splice(0, drop);
    }
  }

  private tick(): void {
    if (this.stopped) return;
    const end = this.serverNow();
    const start = end - this.o.windowMs;
    const window = this.buffer.filter((e) => e.ts_ms >= start && e.ts_ms <= end);
    const seenBefore = [...this.firstSeen.entries()]
      .filter(([, ts]) => ts < start)
      .map(([a]) => a);
    const authorOf = new Map<string, string>();
    for (const e of window) authorOf.set(e.id, e.author);
    const groups: LiveGroup[] = groupChat(window).map((g) => ({
      ...g,
      chatters: new Set(g.event_ids.map((id) => authorOf.get(id))).size,
    }));
    const p = pulse(window, start, end, seenBefore, groups);
    this.o.onTick({
      windowMs: [start, end],
      groups,
      sampled: this.evictedUntil >= start,
      pulse: p,
      messagesTotal: this.messagesTotal,
      windowMessages: window.length,
      serverNow: end,
    });
  }
}

// --- Live source: a real anonymous Twitch IRC socket in the browser --------------------------
export interface LiveSourceOptions {
  WebSocketImpl?: typeof WebSocket;
  url?: string;
  now?: () => number;
  quietAfterMs?: number;
}

export function liveSource(channel: string, opts: LiveSourceOptions = {}): ChatSource {
  let client: TwitchChatClient | null = null;
  return {
    start(onRow, onState) {
      client = new TwitchChatClient({
        channel,
        onRow,
        onState: (s, info) => onState(s, info),
        WebSocketImpl: opts.WebSocketImpl,
        url: opts.url,
        now: opts.now,
        quietAfterMs: opts.quietAfterMs,
      });
      client.start();
    },
    stop() {
      client?.stop();
      client = null;
    },
  };
}

// --- Replay source: a recorded, pseudonymised capture replayed in real time ------------------
// It is NOT live and says so: it reports state "replay". It exists so the demo always has a busy
// chat to show when no streamer the visitor knows is live. Never used as a silent fallback for a
// failed live connection — the caller chooses replay explicitly.
export interface ReplayRow {
  id: string;
  ts_ms: number;
  login: string; // already pseudonymised in the committed fixture
  text: string;
}

export interface ReplayOptions {
  now?: () => number;
  setTimeoutImpl?: (fn: () => void, ms: number) => ReturnType<typeof setTimeout>;
  loop?: boolean;
  speed?: number; // 1 = real time
}

export function replaySource(rows: ReplayRow[], opts: ReplayOptions = {}): ChatSource {
  const now = opts.now ?? (() => Date.now());
  const setT = opts.setTimeoutImpl ?? ((fn, ms) => setTimeout(fn, ms));
  const speed = opts.speed ?? 1;
  let timers: ReturnType<typeof setTimeout>[] = [];
  let stopped = false;

  const run = (onRow: (r: ChatRow) => void, onState: (s: SourceState) => void, base: number) => {
    if (rows.length === 0) {
      onState("ended");
      return;
    }
    const t0 = rows[0].ts_ms;
    const anchor = now(); // map the recording's timeline onto real time starting now
    onState("replay");
    rows.forEach((r) => {
      const delay = Math.max(0, (r.ts_ms - t0) / speed);
      timers.push(
        setT(() => {
          if (stopped) return;
          // Re-stamp onto the live wall clock so windows and "x ago" read correctly, while the
          // relative spacing of the recording is preserved exactly.
          const ts = anchor + delay + (base - anchor);
          onRow({
            id: `${r.id}#${base}`,
            ts_ms: Math.round(ts),
            login: r.login,
            text: r.text,
            user_type: "",
            room_id: null,
            reply_to: null,
          });
        }, delay),
      );
    });
    const span = (rows[rows.length - 1].ts_ms - t0) / speed;
    if (opts.loop) {
      timers.push(
        setT(() => {
          if (!stopped) run(onRow, onState, now());
        }, span + 1_000),
      );
    } else {
      timers.push(setT(() => !stopped && onState("ended"), span + 500));
    }
  };

  return {
    start(onRow, onState) {
      stopped = false;
      run(onRow, onState, now());
    },
    stop() {
      stopped = true;
      timers.forEach(clearTimeout);
      timers = [];
    },
  };
}
