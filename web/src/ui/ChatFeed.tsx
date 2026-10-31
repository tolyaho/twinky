import { useEffect, useRef, useState } from "react";
import type { ChatEvent } from "../cluster/types";
import { ago } from "./format";

interface Props {
  feed: ChatEvent[];
  now: number;
  highlightIds: Set<string>;
  selectedLabel: string | null;
}

export function ChatFeed({ feed, now, highlightIds, selectedLabel }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const [following, setFollowing] = useState(true);

  useEffect(() => {
    if (following && ref.current) ref.current.scrollTop = ref.current.scrollHeight;
  }, [feed, following]);

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
      <div
        className="feed"
        ref={ref}
        onScroll={onScroll}
        role="log"
        aria-label="Live chat messages"
        aria-live="off"
      >
        {feed.length === 0 ? (
          <div className="feed-empty">Waiting for the first messages…</div>
        ) : (
          feed.map((m) => {
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
