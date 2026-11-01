import { useEffect, useMemo, useRef, useState } from "react";
import {
  TwinkySession,
  liveSource,
  replaySource,
  streamClock,
  type LiveGroup,
  type ReplayRow,
  type SourceInfo,
  type SourceState,
  type TickSnapshot,
} from "../engine/session";
import type { ChatEvent } from "../cluster/types";
import type { Grouper } from "../engine/session";
import { makeGrouper } from "../semantic/enable";
import { useBroadcast, type Broadcast } from "./broadcast";
import { effectiveStatus } from "./derive";
import { stableOrder } from "./order";

/** The chat connection's state. Whether the broadcast is on air is `broadcast`, separately. */
export type UiStatus = SourceState;

export type Descriptor =
  | { kind: "live"; channel: string }
  | { kind: "replay"; channel: string; rows: ReplayRow[] };

export interface GroupView extends LiveGroup {
  share: number;
  trend: "new" | "up" | "flat" | "down";
  /** Grew sharply since the previous recount — the board gives it a brief emphasis. */
  surge: boolean;
}

const FEED_MAX = 160; // bounded feed: a busy chat never grows the DOM without limit
const FLUSH_MS = 200; // decouple render rate from message rate
const HISTORY = 5; // ticks of per-cluster count history for the trend arrow

export interface SessionView {
  status: UiStatus;
  statusInfo: SourceInfo | null;
  broadcast: Broadcast;
  source: "live" | "replay";
  channel: string;
  feed: ChatEvent[];
  tick: TickSnapshot | null;
  groups: GroupView[];
  selectedKey: string | null;
  highlightIds: Set<string>;
  select: (key: string | null) => void;
  messagesTotal: number;
  elapsedMs: number;
  windowMs: number;
  setWindowMs: (ms: number) => void;
}

/** The recorded example plays faster than it happened, so a short visit sees it move. */
export const REPLAY_SPEED = 3;

/** A sharp rise: at least three more messages, and at least a quarter more than last time. */
export function isSurge(prev: number | undefined, now: number): boolean {
  if (prev === undefined) return false;
  return now - prev >= Math.max(3, Math.ceil(prev * 0.25));
}

export interface UseSessionOptions {
  /** how a window becomes groups; the page's choice (src/semantic/enable.ts) by default */
  grouper?: (channel: string) => Grouper | undefined;
  /** the window to start with */
  windowMs?: number;
}

export function useSession(descriptor: Descriptor | null, opts: UseSessionOptions = {}): SessionView {
  const [ircStatus, setStatus] = useState<UiStatus>("idle");
  const [statusInfo, setStatusInfo] = useState<SourceInfo | null>(null);
  const [tick, setTick] = useState<TickSnapshot | null>(null);
  const [feed, setFeed] = useState<ChatEvent[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);
  const [windowMs, setWindowState] = useState(opts.windowMs ?? 60_000);
  const windowRef = useRef(opts.windowMs ?? 60_000);
  const makeGrouperRef = useRef(opts.grouper ?? makeGrouper);

  const sessionRef = useRef<TwinkySession | null>(null);
  const feedBuf = useRef<ChatEvent[]>([]);
  const dirty = useRef(false);
  const latestTick = useRef<TickSnapshot | null>(null);
  const history = useRef(new Map<string, number[]>());
  const order = useRef<string[]>([]);
  const startedAt = useRef(0);

  const key = descriptor
    ? descriptor.kind === "live"
      ? `live:${descriptor.channel}`
      : `replay:${descriptor.channel}`
    : null;

  useEffect(() => {
    if (!descriptor) return;
    // reset for a fresh session — nothing from the previous channel leaks in
    feedBuf.current = [];
    latestTick.current = null;
    history.current = new Map();
    order.current = [];
    startedAt.current = Date.now();
    setFeed([]);
    setTick(null);
    setSelectedKey(null);
    setStatus(descriptor.kind === "replay" ? "replay" : "connecting");
    setStatusInfo(descriptor.kind === "live" ? { phase: "opening" } : null);
    setElapsedMs(0);

    // A recorded 7-minute capture, played faster so the audience waves form within seconds.
    // Same messages, same order, same spacing — only the clock runs faster, and the session reads
    // that clock, so every time and rate on screen is the recording's. Clearly labelled REPLAY.
    const clock = descriptor.kind === "replay" ? streamClock(REPLAY_SPEED) : undefined;
    const source =
      descriptor.kind === "live"
        ? liveSource(descriptor.channel)
        : replaySource(descriptor.rows, { loop: true, speed: REPLAY_SPEED, now: clock });

    const session = new TwinkySession({
      source,
      now: clock,
      // grouping by meaning when the browser can run it; the word rules otherwise
      grouper: makeGrouperRef.current(descriptor.channel),
      windowMs: windowRef.current,
      onChat: (e) => {
        feedBuf.current.push(e);
        if (feedBuf.current.length > FEED_MAX) {
          feedBuf.current.splice(0, feedBuf.current.length - FEED_MAX);
        }
        dirty.current = true;
      },
      onTick: (snap) => {
        // roll per-cluster count history for the trend arrow — even while hidden, so trends stay true
        const next = new Map<string, number[]>();
        for (const g of snap.groups) {
          const prev = history.current.get(g.key) ?? [];
          next.set(g.key, [...prev, g.count].slice(-HISTORY));
        }
        history.current = next;
        latestTick.current = snap;
        // A hidden tab paints nothing; skip the render and catch up when it is visible again.
        if (!document.hidden) setTick(snap);
      },
      onState: (s, info) => {
        setStatus(s);
        setStatusInfo(info ?? null);
      },
    });
    sessionRef.current = session;
    session.start();

    const flush = () => {
      if (dirty.current) {
        dirty.current = false;
        setFeed(feedBuf.current.slice());
      }
      setElapsedMs(Date.now() - startedAt.current);
    };
    const timer = setInterval(() => {
      if (!document.hidden) flush();
    }, FLUSH_MS);
    const onVisible = () => {
      if (document.hidden) return;
      flush();
      if (latestTick.current) setTick(latestTick.current);
    };
    document.addEventListener("visibilitychange", onVisible);

    return () => {
      clearInterval(timer);
      document.removeEventListener("visibilitychange", onVisible);
      session.stop();
      sessionRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // Optional authoritative broadcast status; "unknown" whenever it cannot be established.
  const broadcast = useBroadcast(
    descriptor?.kind === "live" ? descriptor.channel : null,
    descriptor?.kind === "live",
  );

  const groups: GroupView[] = useMemo(() => {
    if (!tick) return [];
    const wm = tick.windowMessages || 0;
    const views = tick.groups.map((g) => {
      const hist = history.current.get(g.key) ?? [g.count];
      let trend: GroupView["trend"] = "flat";
      if (hist.length <= 2) trend = "new";
      else {
        const older = hist[0];
        if (g.count > older * 1.15) trend = "up";
        else if (g.count < older * 0.85) trend = "down";
      }
      return {
        ...g,
        share: wm ? g.count / wm : 0,
        trend,
        surge: isSurge(hist.length >= 2 ? hist[hist.length - 2] : undefined, g.count),
      };
    });
    const stable = stableOrder(views, order.current);
    order.current = stable.map((g) => g.key);
    return stable;
  }, [tick]);

  const highlightIds = useMemo(() => {
    if (!selectedKey || !tick) return new Set<string>();
    const g = tick.groups.find((x) => x.key === selectedKey);
    return new Set(g?.event_ids ?? []);
  }, [selectedKey, tick]);

  const setWindowMs = (ms: number) => {
    windowRef.current = ms;
    setWindowState(ms);
    history.current = new Map(); // trends across a window change would compare different spans
    order.current = []; // a different window is a different ranking; start from true rank
    sessionRef.current?.setWindow(ms);
  };

  return {
    status: effectiveStatus(ircStatus, broadcast),
    statusInfo,
    broadcast,
    source: descriptor?.kind === "replay" ? "replay" : "live",
    channel: descriptor?.channel ?? "",
    feed,
    tick,
    groups,
    selectedKey,
    highlightIds,
    select: setSelectedKey,
    messagesTotal: tick?.messagesTotal ?? 0,
    elapsedMs,
    windowMs,
    setWindowMs,
  };
}
