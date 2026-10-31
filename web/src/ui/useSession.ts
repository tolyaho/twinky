import { useEffect, useMemo, useRef, useState } from "react";
import {
  TwinkySession,
  liveSource,
  replaySource,
  type ReplayRow,
  type SourceInfo,
  type SourceState,
  type TickSnapshot,
} from "../engine/session";
import type { ChatEvent, Group } from "../cluster/types";

export type UiStatus = SourceState | "offline" | "not_found";

export type Descriptor =
  | { kind: "live"; channel: string }
  | { kind: "replay"; channel: string; rows: ReplayRow[] };

export interface GroupView extends Group {
  share: number;
  trend: "new" | "up" | "flat" | "down";
}

const FEED_MAX = 160; // bounded feed: a busy chat never grows the DOM without limit
const FLUSH_MS = 200; // decouple render rate from message rate
const HISTORY = 5; // ticks of per-cluster count history for the trend arrow

export interface SessionView {
  status: UiStatus;
  statusInfo: SourceInfo | null;
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
}

export function useSession(descriptor: Descriptor | null): SessionView {
  const [status, setStatus] = useState<UiStatus>("idle");
  const [statusInfo, setStatusInfo] = useState<SourceInfo | null>(null);
  const [tick, setTick] = useState<TickSnapshot | null>(null);
  const [feed, setFeed] = useState<ChatEvent[]>([]);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const [elapsedMs, setElapsedMs] = useState(0);

  const sessionRef = useRef<TwinkySession | null>(null);
  const feedBuf = useRef<ChatEvent[]>([]);
  const dirty = useRef(false);
  const history = useRef(new Map<string, number[]>());
  const startedAt = useRef(0);
  const statusApi = useRef<UiStatus | null>(null); // authoritative override, when available

  const key = descriptor
    ? descriptor.kind === "live"
      ? `live:${descriptor.channel}`
      : `replay:${descriptor.channel}`
    : null;

  useEffect(() => {
    if (!descriptor) return;
    // reset for a fresh session — nothing from the previous channel leaks in
    feedBuf.current = [];
    history.current = new Map();
    statusApi.current = null;
    startedAt.current = Date.now();
    setFeed([]);
    setTick(null);
    setSelectedKey(null);
    setStatus(descriptor.kind === "replay" ? "replay" : "connecting");
    setStatusInfo(null);
    setElapsedMs(0);

    const source =
      descriptor.kind === "live"
        ? liveSource(descriptor.channel)
        : // A recorded 7-minute capture, compressed so the audience waves form within seconds.
          // Same messages, same order — only the playback clock is faster. Clearly labelled REPLAY.
          replaySource(descriptor.rows, { loop: true, speed: 3 });

    const session = new TwinkySession({
      source,
      onChat: (e) => {
        feedBuf.current.push(e);
        if (feedBuf.current.length > FEED_MAX) {
          feedBuf.current.splice(0, feedBuf.current.length - FEED_MAX);
        }
        dirty.current = true;
      },
      onTick: (snap) => {
        // roll per-cluster count history for the trend arrow
        const next = new Map<string, number[]>();
        for (const g of snap.groups) {
          const prev = history.current.get(g.key) ?? [];
          next.set(g.key, [...prev, g.count].slice(-HISTORY));
        }
        history.current = next;
        setTick(snap);
      },
      onState: (s, info) => {
        // an authoritative offline/not_found from the status API wins over IRC's "quiet"
        if (statusApi.current && (s === "quiet" || s === "connected")) {
          setStatus(statusApi.current);
        } else {
          setStatus(s as UiStatus);
        }
        setStatusInfo(info ?? null);
      },
    });
    sessionRef.current = session;
    session.start();

    const flush = setInterval(() => {
      if (dirty.current) {
        dirty.current = false;
        setFeed(feedBuf.current.slice());
      }
      setElapsedMs(Date.now() - startedAt.current);
    }, FLUSH_MS);

    return () => {
      clearInterval(flush);
      session.stop();
      sessionRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  // Optional authoritative channel status (serverless Helix check). Degrades silently when the
  // endpoint is absent/unconfigured — the IRC-only states remain correct on their own.
  useEffect(() => {
    if (!descriptor || descriptor.kind !== "live") return;
    let cancelled = false;
    const ac = new AbortController();
    fetch(`/api/twitch-status?login=${encodeURIComponent(descriptor.channel)}`, {
      signal: ac.signal,
    })
      .then((r) => (r.ok ? r.json() : null))
      .then((data: { state?: string } | null) => {
        if (cancelled || !data) return;
        if (data.state === "offline" || data.state === "not_found") {
          statusApi.current = data.state;
          setStatus((cur) =>
            cur === "quiet" || cur === "connected" || cur === "connecting"
              ? (data.state as UiStatus)
              : cur,
          );
        } else if (data.state === "live") {
          statusApi.current = null; // authoritative live — let IRC states (receiving/quiet) show
        }
      })
      .catch(() => {
        /* no status endpoint configured — fine, IRC states stand on their own */
      });
    return () => {
      cancelled = true;
      ac.abort();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);

  const groups: GroupView[] = useMemo(() => {
    if (!tick) return [];
    const wm = tick.windowMessages || 0;
    return tick.groups.map((g) => {
      const hist = history.current.get(g.key) ?? [g.count];
      let trend: GroupView["trend"] = "flat";
      if (hist.length <= 2) trend = "new";
      else {
        const older = hist[0];
        if (g.count > older * 1.15) trend = "up";
        else if (g.count < older * 0.85) trend = "down";
      }
      return { ...g, share: wm ? g.count / wm : 0, trend };
    });
  }, [tick]);

  const highlightIds = useMemo(() => {
    if (!selectedKey || !tick) return new Set<string>();
    const g = tick.groups.find((x) => x.key === selectedKey);
    return new Set(g?.event_ids ?? []);
  }, [selectedKey, tick]);

  return {
    status,
    statusInfo,
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
  };
}
