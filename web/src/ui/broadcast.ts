// Whether the broadcaster is on air — a different question from whether chat is connected.
//
// Anonymous IRC joins an offline channel exactly as it joins a live one, so the chat socket can
// never answer this. The answer comes only from `/api/twitch-status` (Helix, server-side
// credentials). When that is unconfigured or unreachable the state is "unknown" and the page says
// so; silence, timeouts and network errors are never turned into "offline".
import { useEffect, useState } from "react";

export type BroadcastState = "live" | "offline" | "not_found" | "unknown";

export interface Broadcast {
  state: BroadcastState;
  /** null until the endpoint has answered; false when no Twitch app is configured. */
  configured: boolean | null;
  /** When Twitch was actually asked (server clock), for honest freshness. */
  checkedAt: number | null;
  /** When the current broadcast started, if live. */
  startedAt: number | null;
}

export const UNKNOWN: Broadcast = { state: "unknown", configured: null, checkedAt: null, startedAt: null };

const DEFAULT_RECHECK_MS = 60_000;
const MIN_RECHECK_MS = 250;
const RETRY_MS = 60_000; // after a failed check
/** An authoritative answer older than this is no longer shown as one. */
export const STALE_MS = 180_000;

interface Body {
  state?: string;
  configured?: boolean;
  checkedAt?: number;
  startedAt?: number;
  recheckAfterMs?: number;
}

/** Parse the endpoint's answer. Anything unexpected is "unknown", never a guess. */
export function readStatus(body: Body | null): { b: Broadcast; recheckMs: number | null } {
  if (!body || typeof body !== "object") return { b: UNKNOWN, recheckMs: RETRY_MS };
  const state: BroadcastState =
    body.state === "live" || body.state === "offline" || body.state === "not_found"
      ? body.state
      : "unknown";
  const configured = typeof body.configured === "boolean" ? body.configured : null;
  const b: Broadcast = {
    state,
    configured,
    checkedAt: typeof body.checkedAt === "number" ? body.checkedAt : null,
    startedAt: state === "live" && typeof body.startedAt === "number" ? body.startedAt : null,
  };
  // Unconfigured will not change while the page is open: stop asking.
  if (configured === false) return { b, recheckMs: null };
  const r = typeof body.recheckAfterMs === "number" ? body.recheckAfterMs : DEFAULT_RECHECK_MS;
  return { b, recheckMs: Math.max(MIN_RECHECK_MS, r) };
}

/**
 * Poll the status endpoint for `channel`. Each channel gets a fresh epoch: an answer that arrives
 * after the visitor has switched away is dropped, so a slow "offline" for the old channel can
 * never land on the new one. Checks pause while the tab is hidden.
 */
export function useBroadcast(channel: string | null, enabled: boolean): Broadcast {
  const [b, setB] = useState<Broadcast>(UNKNOWN);

  useEffect(() => {
    setB(UNKNOWN);
    if (!channel || !enabled) return;
    let alive = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let ac: AbortController | null = null;
    let due = 0; // when the next check is due (local clock)

    const schedule = (ms: number) => {
      due = Date.now() + ms;
      timer = setTimeout(() => {
        if (!document.hidden) void check();
        // hidden: the visibility handler checks on return
      }, ms);
    };

    const check = async () => {
      ac?.abort();
      ac = new AbortController();
      try {
        const r = await fetch(`/api/twitch-status?login=${encodeURIComponent(channel)}`, {
          signal: ac.signal,
          cache: "no-store",
        });
        const body = r.ok ? ((await r.json()) as Body) : null;
        if (!alive) return; // switched channel or unmounted while in flight
        const { b: next, recheckMs } = readStatus(body);
        if (body) setB(next);
        else ageOut();
        if (recheckMs !== null) schedule(recheckMs);
      } catch {
        if (!alive) return;
        ageOut();
        schedule(RETRY_MS);
      }
    };

    // A failed re-check keeps the last real answer until it is too old to stand on.
    const ageOut = () =>
      setB((prev) =>
        prev.checkedAt !== null && Date.now() - prev.checkedAt > STALE_MS
          ? { ...UNKNOWN, configured: prev.configured }
          : prev,
      );

    const onVisible = () => {
      if (!document.hidden && due && Date.now() >= due) {
        clearTimeout(timer);
        void check();
      }
    };
    document.addEventListener("visibilitychange", onVisible);
    void check();

    return () => {
      alive = false;
      ac?.abort();
      clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisible);
    };
  }, [channel, enabled]);

  return b;
}
