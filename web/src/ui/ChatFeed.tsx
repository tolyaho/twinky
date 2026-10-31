import { useEffect, useRef, useState } from "react";
import type { ChatEvent } from "../cluster/types";
import { ago } from "./format";

interface Props {
  feed: ChatEvent[];
  now: number;
  highlightIds: Set<string>;
  selectedLabel: string | null;
  emptyText: string;
}

export function ChatFeed({ feed, now, highlightIds, selectedLabel, emptyText }: Props) {
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

  useEffect(() => {
    if (following && ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [shown, following]);

  const onScroll = () => {
    const el = ref.current;
    if (!el) return;
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 48;
    if (atBottom !== following) setFollowing(atBottom);
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
          {frozen ? "▶ Resume" : "❚❚ Pause"}
        </button>
        {frozen && (
          <span className="feed-behind">
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
          <div className="feed-empty">{emptyText}</div>
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
          ↓ Follow live
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
