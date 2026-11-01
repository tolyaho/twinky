// The on-stream overlay: what chat is saying, shown back to the viewers who are saying it.
//
// It is its own page (`/?channel=xqc&overlay=1`), because an OBS Browser Source is a separate
// browser that shares nothing with a dashboard someone may have open: it connects to the
// channel's chat itself, anonymously and read-only, exactly as the dashboard does. The page paints
// no background of its own, so OBS composites it straight over the video.
import { useEffect, useLayoutEffect, useRef, type ReactNode } from "react";
import type { SemanticInfo } from "../semantic/live";
import { makeOverlayGrouper } from "../semantic/enable";
import { normalizeChannel } from "../twitch/parse";
import { WINDOWS, compact, windowShort } from "./format";
import { EASE_OUT, motionAllowed } from "./motion";
import { useSession, type GroupView, type UiStatus } from "./useSession";

export const OVERLAY_ROWS = 3;

/** What the overlay URL asks for. `null` when this page is not the overlay. */
export interface OverlayRoute {
  channel: string; // "" when the URL names none, or names something that is not a channel
  /** what the URL said, to repeat it back when it is not a channel name */
  asked: string;
  windowMs: number;
}

export function overlayFromUrl(search = window.location.search): OverlayRoute | null {
  const q = new URLSearchParams(search);
  if (!q.has("overlay") || q.get("overlay") === "0") return null;
  const w = WINDOWS.find((x) => x.short === q.get("window"));
  const asked = (q.get("channel") ?? "").trim();
  return { channel: normalizeChannel(asked) ?? "", asked, windowMs: w?.ms ?? 60_000 };
}

/** The link a streamer pastes into OBS. Read-only chat, no key, no account. */
export function overlayUrl(origin: string, channel: string, opts: { light?: boolean; windowMs?: number } = {}): string {
  const q = new URLSearchParams({ channel, overlay: "1" });
  if (opts.windowMs && opts.windowMs !== 60_000) q.set("window", windowShort(opts.windowMs));
  if (opts.light) q.set("topics", "off");
  return `${origin}/?${q.toString()}`;
}

const KIND: Record<string, string> = {
  reaction: "reaction",
  phrase: "repeated",
  topic: "topic",
  question: "question",
  words: "one-word replies",
  prefix: "variants",
  token: "shared word",
};

/** One short line for whatever is not a list of groups: connecting, quiet, no such channel… */
function statusLine(status: UiStatus, channel: string, hasGroups: boolean): string | null {
  switch (status) {
    case "not_found":
      return `No Twitch channel called #${channel}`;
    case "no_network":
    case "error":
    case "reconnecting":
      return "Reconnecting to chat…";
    case "closed":
      return "Disconnected from chat";
    case "idle":
    case "connecting":
      return `Connecting to #${channel} chat…`;
    case "quiet":
      return hasGroups ? null : `#${channel} chat is quiet`;
    default:
      return hasGroups ? null : `Listening to #${channel} chat`;
  }
}

/** Rows slide to a new place when the ranking changes; nothing else moves. */
function useRowSlide(keys: string) {
  const items = useRef(new Map<string, HTMLLIElement>());
  const tops = useRef(new Map<string, number>());
  useLayoutEffect(() => {
    const next = new Map<string, number>();
    items.current.forEach((el, k) => {
      next.set(k, el.offsetTop);
      const was = tops.current.get(k);
      if (was !== undefined && Math.abs(was - el.offsetTop) > 1 && motionAllowed() && typeof el.animate === "function")
        el.animate([{ transform: `translateY(${was - el.offsetTop}px)` }, { transform: "none" }], { duration: 420, easing: EASE_OUT });
    });
    tops.current = next;
  }, [keys]);
  return (k: string) => (el: HTMLLIElement | null) => {
    if (el) items.current.set(k, el);
    else items.current.delete(k);
  };
}

export function OverlayView({
  channel,
  groups,
  status,
  semantic,
  windowMs,
  rows = OVERLAY_ROWS,
}: {
  channel: string;
  groups: GroupView[];
  status: UiStatus;
  semantic?: SemanticInfo;
  windowMs: number;
  rows?: number;
}) {
  const top = groups.slice(0, rows);
  const line = statusLine(status, channel, top.length > 0);
  const ref = useRowSlide(top.map((g) => g.key).join("|"));
  // said plainly while there are no topics: what is shown is reactions and repeats
  const mode =
    semantic?.state === "loading" ? "finding topics…" : semantic && semantic.state !== "ready" ? "reactions & repeats" : null;
  const busy = status === "connecting" || status === "idle" || status === "reconnecting" || status === "no_network" || status === "error";
  return (
    <div className="ov" role="region" aria-label={`What #${channel} chat is saying`}>
      <div className="ov-card">
        <div className="ov-head">
          <span className="ov-brand">
            Twinky<span className="wordmark-dot">.</span>
          </span>
          <span className="ov-chan">#{channel} chat</span>
          <span className="ov-win">
            {mode ? `${mode} · ` : ""}last {windowShort(windowMs)}
          </span>
        </div>
        {top.length > 0 && (
          <ol className="ov-list">
            {top.map((g) => (
              <li key={g.key} ref={ref(g.key)} className="ov-row">
                <span className="ov-n">{compact(g.count)}</span>
                <span className="ov-main">
                  <span className="ov-label">{g.display}</span>
                  <span className="ov-meta">
                    {compact(g.chatters)} {g.chatters === 1 ? "person" : "people"} · {KIND[g.rule] ?? g.rule}
                  </span>
                </span>
                <span className="ov-bar" aria-hidden="true">
                  <span style={{ transform: `scaleX(${Math.max(0.04, Math.min(1, g.share))})` }} />
                </span>
              </li>
            ))}
          </ol>
        )}
        {line && (
          <p className={`ov-status${status === "not_found" ? " ov-status-bad" : ""}`} role="status">
            {busy && <span className="listening" aria-hidden="true" />}
            {line}
          </p>
        )}
      </div>
    </div>
  );
}

function Setup({ children }: { children: ReactNode }) {
  return (
    <div className="ov">
      <div className="ov-card ov-help">{children}</div>
    </div>
  );
}

/** The standalone overlay page. Nothing from a dashboard is shared: this is its own session. */
export function OverlayPage({ route }: { route: OverlayRoute }) {
  useEffect(() => {
    // no page background: OBS draws the video underneath
    document.documentElement.classList.add("overlay-page");
    document.title = route.channel ? `#${route.channel} · Twinky overlay` : "Twinky overlay";
  }, [route.channel]);
  const view = useSession(route.channel ? { kind: "live", channel: route.channel } : null, {
    grouper: makeOverlayGrouper,
    windowMs: route.windowMs,
  });
  if (!route.channel) {
    return (
      <Setup>
        <strong>Twinky overlay</strong> —{" "}
        {route.asked ? `“${route.asked}” is not a Twitch channel name. ` : "no channel in the address. "}
        Use <code>?channel=yourname&amp;overlay=1</code>
      </Setup>
    );
  }
  return (
    <OverlayView
      channel={route.channel}
      groups={view.groups}
      status={view.status}
      semantic={view.tick?.semantic}
      windowMs={view.windowMs}
    />
  );
}
