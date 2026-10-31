import { useEffect, useLayoutEffect, useRef, useState } from "react";
import type { ChatEvent } from "../cluster/types";
import { ago } from "./format";
import { EASE_OUT, motionAllowed } from "./motion";

interface Props {
  feed: ChatEvent[];
  now: number;
  highlightIds: Set<string>;
  selectedLabel: string | null;
  emptyText: string;
  /** Still working towards messages (connecting, joined, reconnecting) — not a terminal state. */
  waiting: boolean;
}

const ANIMATE_MAX = 12; // in a burst only the newest few slide in; the rest just appear

export function ChatFeed({ feed, now, highlightIds, selectedLabel, emptyText, waiting }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [following, setFollowing] = useState(true);
  // Pause freezes what is on screen so a message can actually be read. Counting never pauses —
  // the clusters and pulse keep running on the full stream.
  const [frozen, setFrozen] = useState<ChatEvent[] | null>(null);
  const shown = frozen ?? feed;
  const lastShown = shown.length ? shown[shown.length - 1].id : null;
  // How far the live feed has moved past the frozen view. -1: the last frozen message has already
  // scrolled out of the bounded feed, so the exact number is unknown.
  const at = frozen ? feed.findIndex((m) => m.id === lastShown) : 0;
  const behind = at === -1 ? -1 : feed.length - 1 - at;

  // New messages while scrolled up: counted from the last one on screen when following stopped.
  const anchor = useRef<string | null>(null);
  const sinceAnchor = (() => {
    if (following || !anchor.current) return 0;
    const i = feed.findIndex((m) => m.id === anchor.current);
    return i === -1 ? -1 : feed.length - 1 - i;
  })();

  // Animate only the messages that were not on screen last render. They are always the tail.
  const seen = useRef(new Set<string>());
  useLayoutEffect(() => {
    const el = ref.current;
    const fresh = shown.filter((m) => !seen.current.has(m.id)).length;
    seen.current = new Set(shown.map((m) => m.id));
    if (!el || fresh === 0 || !motionAllowed()) return;
    const kids = el.children;
    for (let i = Math.max(0, kids.length - Math.min(fresh, ANIMATE_MAX)); i < kids.length; i++) {
      (kids[i] as HTMLElement).animate(
        [
          { opacity: 0, transform: "translateY(4px)" },
          { opacity: 1, transform: "none" },
        ],
        { duration: 180, easing: EASE_OUT },
      );
    }
  }, [shown]);

  useEffect(() => {
    if (following && ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [shown, following]);

  const onScroll = () => {
    const el = ref.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
    if (atBottom !== following) {
      if (!atBottom) anchor.current = shown.length ? shown[shown.length - 1].id : null;
      setFollowing(atBottom);
    }
  };

  const follow = () => {
    setFollowing(true);
    if (ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  };

  const hasHighlight = highlightIds.size > 0;

  return (
    <div className="feed-wrap">
      {(feed.length > 0 || frozen) && (
        <div className="feed-controls">
          <button
            className="btn-ghost"
            onClick={() => setFrozen(frozen ? null : feed.slice())}
            aria-pressed={frozen !== null}
          >
            <svg className="btn-icon" viewBox="0 0 10 10" aria-hidden="true">
              {frozen ? (
                <path d="M2 1.2v7.6a.5.5 0 0 0 .76.43l6.1-3.8a.5.5 0 0 0 0-.86L2.76.77A.5.5 0 0 0 2 1.2z" />
              ) : (
                <>
                  <rect x="1.5" y="1" width="2.6" height="8" rx="0.8" />
                  <rect x="5.9" y="1" width="2.6" height="8" rx="0.8" />
                </>
              )}
            </svg>
            {frozen ? "Resume" : "Pause"}
          </button>
          {frozen && (
            <span className="feed-behind" role="status">
              {behind === -1 ? `${feed.length}+` : behind} new while paused
            </span>
          )}
        </div>
      )}
      <div
        className="feed"
        ref={ref}
        onScroll={onScroll}
        role="log"
        aria-label="Live chat messages"
        aria-live="off"
      >
        {shown.length === 0 ? (
          <div className="feed-empty">
            {waiting && <span className="listening" aria-hidden="true" />}
            {emptyText}
          </div>
        ) : (
          shown.map((m) => {
            const lit = highlightIds.has(m.id);
            return (
              <div
                key={m.id}
                className={`msg${lit ? " msg-lit" : ""}${hasHighlight && !lit ? " msg-dim" : ""}`}
              >
                <span className="msg-author">{m.author}</span>
                <span className="msg-text">{m.text}</span>
                <span className="msg-time" aria-hidden="true">
                  {ago(now - m.ts_ms)}
                </span>
              </div>
            );
          })
        )}
      </div>
      {!following && (
        <button className="follow-live" onClick={follow}>
          ↓ {sinceAnchor === 0 ? "Follow live" : `${sinceAnchor === -1 ? `${feed.length}+` : sinceAnchor} new · follow live`}
        </button>
      )}
      {selectedLabel && (
        <div className="feed-filter-note">
          Highlighting <strong>{selectedLabel}</strong>
        </div>
      )}
    </div>
  );
}
