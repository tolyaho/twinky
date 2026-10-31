// A browser-side anonymous Twitch IRC client. Connects directly to Twitch over WebSocket with the
// anonymous `justinfan` login (read-only public chat, no credentials) — the same handshake the
// Python `live_chat.py`/`capture.py` use, run in the visitor's own browser so there is no server
// to hold the socket open.
//
// It owns the full connection lifecycle and reports honest states. In particular it NEVER claims
// the broadcaster is "live": anonymous IRC joins an offline channel just as happily as a live one,
// so the strongest truthful claim here is "connected" / "receiving messages" / "quiet". Authoritative
// live/offline/not-found status, when available, is layered on separately by the session engine.
import { parsePrivmsg, type ChatRow } from "./parse";

export const TWITCH_WS = "wss://irc-ws.chat.twitch.tv:443";

export type IrcState =
  | "idle"
  | "connecting"
  | "connected" // JOIN acknowledged (366), no messages yet
  | "receiving" // messages are arriving
  | "quiet" // connected, but silent for a while (often offline)
  | "reconnecting"
  | "not_found" // Twitch never acknowledged the JOIN, or reported the channel suspended
  | "no_network" // the browser reports it is offline; we resume the moment it is back
  | "error"
  | "closed";

/** The slice of `window` the client watches for connectivity changes. Injectable for tests. */
export interface NetworkEvents {
  addEventListener(type: "online" | "offline", fn: () => void): void;
  removeEventListener(type: "online" | "offline", fn: () => void): void;
  readonly navigator?: { readonly onLine?: boolean };
}

/** The IRC command of a line: tags and prefix stripped. `@a=b :x!y@z PRIVMSG #c :hi` -> PRIVMSG */
export function ircCommand(line: string): string {
  let s = line;
  if (s.startsWith("@")) s = s.slice(s.indexOf(" ") + 1);
  if (s.startsWith(":")) s = s.slice(s.indexOf(" ") + 1);
  const sp = s.indexOf(" ");
  return sp === -1 ? s : s.slice(0, sp);
}

export interface IrcStateInfo {
  message?: string;
  attempt?: number;
  /** While connecting: still reaching Twitch, or reached it and waiting for the JOIN answer. */
  phase?: "opening" | "joining";
}

export interface IrcOptions {
  channel: string;
  onRow: (row: ChatRow) => void;
  onState: (state: IrcState, info?: IrcStateInfo) => void;
  /** Injectable for tests; defaults to the global WebSocket. */
  WebSocketImpl?: typeof WebSocket;
  now?: () => number;
  url?: string;
  quietAfterMs?: number;
  pingIntervalMs?: number;
  stallTimeoutMs?: number;
  baseBackoffMs?: number;
  maxBackoffMs?: number;
  /** Max message ids retained for dedupe after reconnect. */
  dedupeMax?: number;
  /**
   * How long to wait for Twitch to acknowledge the JOIN. With the `twitch.tv/commands` capability
   * an existing channel (live or offline) answers with ROOMSTATE + 366 within ~1s; a channel that
   * does not exist answers with nothing at all. Measured 2026-10-31 against xqc, kaicenat
   * (offline) and two invented names.
   */
  joinTimeoutMs?: number;
  /** Where `online`/`offline` events come from; defaults to `window` in a browser. */
  net?: NetworkEvents | null;
  /** After the network returns, how long a surviving socket has to answer a PING. */
  probeTimeoutMs?: number;
}

type TimerId = ReturnType<typeof setTimeout>;

const defaultNet = (): NetworkEvents | null =>
  typeof window !== "undefined" ? (window as unknown as NetworkEvents) : null;

export class TwitchChatClient {
  private readonly o: Required<
    Omit<IrcOptions, "channel" | "onRow" | "onState" | "net">
  > &
    Pick<IrcOptions, "channel" | "onRow" | "onState"> & { net: NetworkEvents | null };
  private ws: WebSocket | null = null;
  private stopped = false;
  private _state: IrcState = "idle";
  private attempt = 0;
  private sawMessage = false;
  private everJoined = false;
  private joinedThisSocket = false;
  private netDown = false;
  private lastTrafficAt = 0;
  private reconnectTimer?: TimerId;
  private quietTimer?: TimerId;
  private joinTimer?: TimerId;
  private probeTimer?: TimerId;
  private pingTimer?: ReturnType<typeof setInterval>;
  private readonly seen = new Set<string>();
  private readonly seenQueue: string[] = [];

  constructor(opts: IrcOptions) {
    this.o = {
      WebSocketImpl: opts.WebSocketImpl ?? (globalThis.WebSocket as typeof WebSocket),
      now: opts.now ?? (() => Date.now()),
      url: opts.url ?? TWITCH_WS,
      quietAfterMs: opts.quietAfterMs ?? 12_000,
      // A silent dead socket (laptop sleep, dropped Wi-Fi) is noticed within ~70s: we PING every
      // 30s and Twitch answers each one, so two unanswered PINGs means the socket is gone.
      pingIntervalMs: opts.pingIntervalMs ?? 30_000,
      stallTimeoutMs: opts.stallTimeoutMs ?? 70_000,
      baseBackoffMs: opts.baseBackoffMs ?? 1_000,
      maxBackoffMs: opts.maxBackoffMs ?? 30_000,
      dedupeMax: opts.dedupeMax ?? 5_000,
      joinTimeoutMs: opts.joinTimeoutMs ?? 8_000,
      probeTimeoutMs: opts.probeTimeoutMs ?? 5_000,
      net: opts.net === undefined ? defaultNet() : opts.net,
      channel: opts.channel,
      onRow: opts.onRow,
      onState: opts.onState,
    };
  }

  get state(): IrcState {
    return this._state;
  }

  private setState(s: IrcState, info?: IrcStateInfo): void {
    // While the browser says it is offline, every "trying" state is really "no network" — say so,
    // instead of counting reconnect attempts that cannot succeed.
    if (this.netDown && (s === "connecting" || s === "reconnecting" || s === "error" || s === "quiet")) {
      s = "no_network";
      info = { message: "Your device is offline. Twinky reconnects as soon as the network is back." };
    }
    if (s === this._state && s === "no_network") return;
    this._state = s;
    this.o.onState(s, info);
  }

  start(): void {
    this.stopped = false;
    this.netDown = this.o.net?.navigator?.onLine === false;
    this.o.net?.addEventListener("offline", this.onOffline);
    this.o.net?.addEventListener("online", this.onOnline);
    this.open();
  }

  /** Intentional shutdown: no reconnect, socket closed, state -> "closed". */
  stop(): void {
    this.stopped = true;
    this.unlistenNet();
    this.clearTimers();
    this.teardownSocket();
    this.setState("closed");
  }

  private readonly onOffline = (): void => {
    if (this.stopped) return;
    this.netDown = true;
    this.clearReconnect(); // attempts made offline only inflate the backoff
    this.setState("no_network");
  };

  private readonly onOnline = (): void => {
    if (this.stopped || !this.netDown) return;
    this.netDown = false;
    if (this.ws && this.joinedThisSocket) {
      // The socket may have survived the outage, or may be a corpse that has not noticed yet.
      // Ask: any reply within the probe window proves it alive (see onData); silence means
      // reconnect now rather than after the stall watchdog's ~70s.
      this.setState("reconnecting", { message: "Network is back — checking the connection…" });
      this.clearProbe();
      this.send("PING :twinky");
      this.probeTimer = setTimeout(() => {
        this.probeTimer = undefined;
        if (this.stopped) return;
        this.teardownSocket();
        this.scheduleReconnect(0);
      }, this.o.probeTimeoutMs);
    } else {
      // No usable socket: start over immediately with a fresh backoff.
      this.teardownSocket();
      this.attempt = 0;
      this.open();
    }
  };

  private unlistenNet(): void {
    this.o.net?.removeEventListener("offline", this.onOffline);
    this.o.net?.removeEventListener("online", this.onOnline);
  }

  private open(): void {
    this.clearReconnect();
    this.clearProbe();
    this.setState(this.attempt === 0 ? "connecting" : "reconnecting", {
      attempt: this.attempt,
      phase: "opening",
    });
    let ws: WebSocket;
    try {
      ws = new this.o.WebSocketImpl(this.o.url);
    } catch (err) {
      this.setState("error", { message: `Could not open a connection: ${String(err)}` });
      this.scheduleReconnect();
      return;
    }
    this.ws = ws;
    // Guard every handler with socket identity: a torn-down socket must not drive state for the
    // one that replaced it (which would double-fire reconnects on channel switch).
    const mine = () => this.ws === ws;

    ws.addEventListener("open", () => {
      if (!mine()) return;
      // Anonymous handshake. No credentials; `SCHMOOPIIE` is Twitch's documented anonymous pass.
      this.send("PASS SCHMOOPIIE");
      this.send(`NICK justinfan${Math.floor(10_000 + Math.random() * 89_999)}`);
      // `commands` makes Twitch acknowledge a real channel with ROOMSTATE, which is what lets us
      // tell a nonexistent channel apart without any credentials.
      this.send("CAP REQ :twitch.tv/tags twitch.tv/commands");
      this.send(`JOIN #${this.o.channel}`);
      this.lastTrafficAt = this.o.now();
      this.joinedThisSocket = false;
      this.armJoinTimeout();
      this.startPing();
      if (this._state === "connecting" || this._state === "reconnecting") {
        this.setState(this._state, { attempt: this.attempt, phase: "joining" });
      }
    });
    ws.addEventListener("message", (ev: MessageEvent) => {
      if (mine()) this.onData(ev);
    });
    ws.addEventListener("close", () => {
      if (mine()) this.onClose();
    });
    ws.addEventListener("error", () => {
      if (!mine()) return;
      // The browser fires 'error' then 'close'; reconnect is driven by 'close'.
      if (this._state === "connecting") {
        this.setState("error", { message: "Connection failed." });
      }
    });
  }

  private onData(ev: MessageEvent): void {
    this.lastTrafficAt = this.o.now();
    // Bytes arriving prove the network works, whatever the browser's online flag says.
    this.netDown = false;
    if (this.probeTimer !== undefined) {
      this.clearProbe();
      // Alive after the outage. "Connected" until a message proves chat is flowing again.
      this.setState("connected");
      this.armQuiet();
    }
    const raw = typeof ev.data === "string" ? ev.data : String(ev.data);
    for (const line of raw.split("\r\n")) {
      if (!line) continue;
      if (line.startsWith("PING")) {
        this.send("PONG :tmi.twitch.tv");
        continue;
      }
      const cmd = ircCommand(line);
      if (cmd === "RECONNECT") {
        // Twitch is asking us to reconnect to a new edge. Honour it.
        this.teardownSocket();
        this.scheduleReconnect(0);
        return;
      }
      if (cmd === "ROOMSTATE" || cmd === "366") {
        // JOIN acknowledged: the channel exists. Whether the broadcaster is live is still unknown.
        if (!this.joinedThisSocket) {
          this.joinedThisSocket = true;
          this.everJoined = true;
          this.clearJoin();
          this.attempt = 0;
          if (!this.sawMessage) this.setState("connected");
          this.armQuiet();
        }
        continue;
      }
      if (cmd === "NOTICE" && /msg-id=msg_channel_suspended/.test(line)) {
        this.fail("not_found", `#${this.o.channel} is suspended on Twitch.`);
        return;
      }
      if (cmd !== "PRIVMSG") continue; // USERNOTICE, CLEARCHAT etc. are not chat messages
      const row = parsePrivmsg(line);
      if (row && !this.isDuplicate(row.id)) {
        this.sawMessage = true;
        this.attempt = 0;
        this.o.onRow(row);
        this.setState("receiving");
        this.armQuiet();
      }
    }
  }

  private onClose(): void {
    if (this.stopped) return;
    this.ws = null; // closed: nothing left to probe or send on
    this.joinedThisSocket = false;
    this.clearQuiet();
    this.clearJoin();
    this.clearProbe();
    this.stopPing();
    this.scheduleReconnect();
  }

  /** Terminal failure: stop for good (no reconnect loop against a channel that is not there). */
  private fail(state: IrcState, message: string): void {
    this.stopped = true;
    this.unlistenNet();
    this.clearTimers();
    this.teardownSocket();
    this.setState(state, { message });
  }

  // --- helpers ---------------------------------------------------------------------------------

  private armJoinTimeout(): void {
    this.clearJoin();
    this.joinTimer = setTimeout(() => {
      if (this.stopped || this.joinedThisSocket) return;
      if (this.netDown) {
        // No answer because there is no network, not because there is no channel. Drop the
        // socket; the "online" handler opens a fresh one.
        this.teardownSocket();
        return;
      }
      if (this.everJoined) {
        // It existed a minute ago; this is a bad edge, not a missing channel.
        this.teardownSocket();
        this.scheduleReconnect(0);
      } else {
        this.fail(
          "not_found",
          `Twitch did not acknowledge #${this.o.channel} — it most likely does not exist.`,
        );
      }
    }, this.o.joinTimeoutMs);
  }

  private clearJoin(): void {
    if (this.joinTimer !== undefined) clearTimeout(this.joinTimer);
    this.joinTimer = undefined;
  }

  private isDuplicate(id: string): boolean {
    if (this.seen.has(id)) return true;
    this.seen.add(id);
    this.seenQueue.push(id);
    if (this.seenQueue.length > this.o.dedupeMax) {
      const old = this.seenQueue.shift();
      if (old !== undefined) this.seen.delete(old);
    }
    return false;
  }

  private send(s: string): void {
    try {
      this.ws?.send(s);
    } catch {
      /* a send on a dying socket is harmless; 'close' will drive reconnect */
    }
  }

  private armQuiet(): void {
    this.clearQuiet();
    this.quietTimer = setTimeout(() => {
      if (!this.stopped) {
        this.setState("quiet", {
          message: `Connected to #${this.o.channel}, but it has been silent — the channel may be offline, or chat is just slow.`,
        });
      }
    }, this.o.quietAfterMs);
  }

  private startPing(): void {
    this.stopPing();
    this.pingTimer = setInterval(() => {
      if (this.stopped) return;
      // Detect a dead socket even on a silent channel: no inbound traffic at all for too long.
      if (this.o.now() - this.lastTrafficAt > this.o.stallTimeoutMs) {
        this.teardownSocket();
        this.scheduleReconnect(0);
        return;
      }
      this.send("PING :twinky");
    }, this.o.pingIntervalMs);
  }

  private scheduleReconnect(delayOverride?: number): void {
    if (this.stopped) return;
    this.clearReconnect();
    if (this.netDown) {
      // The "online" event reconnects immediately. Keep one slow retry in case the browser's
      // offline flag is wrong (it can stick after VPN or adapter changes) and never clears.
      this.setState("no_network");
      this.reconnectTimer = setTimeout(() => this.open(), this.o.maxBackoffMs);
      return;
    }
    this.attempt += 1;
    const base = Math.min(
      this.o.maxBackoffMs,
      this.o.baseBackoffMs * 2 ** (this.attempt - 1),
    );
    const jitter = base * 0.3 * Math.random();
    const delay = delayOverride ?? base - base * 0.15 + jitter;
    this.setState("reconnecting", { attempt: this.attempt });
    this.reconnectTimer = setTimeout(() => this.open(), Math.max(0, delay));
  }

  private teardownSocket(): void {
    const ws = this.ws;
    this.ws = null;
    this.joinedThisSocket = false;
    this.stopPing();
    if (ws) {
      ws.onopen = ws.onmessage = ws.onclose = ws.onerror = null;
      try {
        ws.close();
      } catch {
        /* ignore */
      }
    }
  }

  private clearReconnect(): void {
    if (this.reconnectTimer !== undefined) clearTimeout(this.reconnectTimer);
    this.reconnectTimer = undefined;
  }

  private clearQuiet(): void {
    if (this.quietTimer !== undefined) clearTimeout(this.quietTimer);
    this.quietTimer = undefined;
  }

  private clearProbe(): void {
    if (this.probeTimer !== undefined) clearTimeout(this.probeTimer);
    this.probeTimer = undefined;
  }

  private stopPing(): void {
    if (this.pingTimer !== undefined) clearInterval(this.pingTimer);
    this.pingTimer = undefined;
  }

  private clearTimers(): void {
    this.clearReconnect();
    this.clearQuiet();
    this.clearJoin();
    this.clearProbe();
    this.stopPing();
  }
}
