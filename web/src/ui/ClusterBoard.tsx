import { useLayoutEffect, useRef, useState } from "react";
import type { ChatEvent } from "../cluster/types";
import { MIN_CHATTERS } from "../engine/session";
import type { GroupView, UiStatus } from "./useSession";
import { WINDOWS, ago, agoPhrase, compact, pct, spanShort, windowLong } from "./format";

interface Props {
  groups: GroupView[];
  /** The window's messages by id — the evidence behind each group. */
  events: ReadonlyMap<string, ChatEvent> | null;
  now: number;
  selectedKey: string | null;
  onSelect: (key: string | null) => void;
  status: UiStatus;
  channel: string;
  windowMessages: number;
  windowMs: number;
  onWindow: (ms: number) => void;
  sampled: boolean;
  soloMessages: number;
  onTryAnother: () => void;
  maxRows?: number;
}

const RULE_CHIP: Record<GroupView["rule"], { chip: string; hint: (g: GroupView) => string }> = {
  reaction: { chip: "reactions", hint: () => "Laughter and emote-only messages, counted as one wave" },
  prefix: {
    chip: "variants",
    hint: (g) => `One-word messages starting with “${g.label.replace(/…$/, "")}”`,
  },
  token: { chip: "shared word", hint: (g) => `Messages containing the word “${g.label}”` },
};

const TREND: Record<GroupView["trend"], { mark: string; cls: string; word: string }> = {
  new: { mark: "●", cls: "t-new", word: "new" },
  up: { mark: "▲", cls: "t-up", word: "growing" },
  flat: { mark: "–", cls: "t-flat", word: "steady" },
  down: { mark: "▼", cls: "t-down", word: "fading" },
};

const EVIDENCE_FIRST = 8; // messages listed when a group opens
const EVIDENCE_MAX = 200; // never render more than this, however big the group
const MAX_ROWS_ALL = 24; // "show all" still has a ceiling

function EmptyState({
  status,
  channel,
  onTryAnother,
}: {
  status: UiStatus;
  channel: string;
  onTryAnother: () => void;
}) {
  let title = "Listening to the room…";
  let body = "Groups appear when several people say the same thing within the window.";
  if (status === "connecting") {
    title = `Connecting to #${channel}`;
    body = "Opening an anonymous connection to Twitch chat.";
  } else if (status === "reconnecting") {
    title = "Reconnecting…";
    body = "The connection to Twitch dropped. Twinky is reconnecting; nothing you have seen is lost.";
  } else if (status === "quiet") {
    title = `#${channel} is quiet`;
    body =
      "No messages for a while. The channel may be offline, or chat is just slow. Try a channel you know is live right now.";
  } else if (status === "offline") {
    title = `#${channel} is offline`;
    body = "There is no live chat to read. Try another channel that is broadcasting.";
  } else if (status === "not_found") {
    title = "No such channel";
    body = `Twitch didn't recognise “${channel}” — it doesn't exist or has been suspended. Check the spelling and try another.`;
  } else if (status === "no_network") {
    title = "You're offline";
    body = "Your device lost its network connection. Twinky will reconnect by itself as soon as it's back.";
  } else if (status === "error") {
    title = "Connection trouble";
    body = "The connection to Twitch failed. Retrying with a short backoff…";
  } else if (status === "closed") {
    title = "Disconnected";
    body = "This session has ended. Pick a channel to start again.";
  } else if (status === "receiving") {
    title = "Chat is flowing";
    body =
      "Nothing has formed a clear group yet — the room is saying lots of different things. Watch this space.";
  }
  return (
    <div className="board-empty">
      <div className="board-empty-title">{title}</div>
      <p className="board-empty-body">{body}</p>
      {(status === "not_found" || status === "offline" || status === "quiet" || status === "closed") && (
        <button className="btn-light" onClick={onTryAnother}>
          Try another channel
        </button>
      )}
    </div>
  );
}

function Evidence({
  g,
  events,
  now,
  onClose,
  id,
}: {
  g: GroupView;
  events: ReadonlyMap<string, ChatEvent> | null;
  now: number;
  onClose: () => void;
  id: string;
}) {
  const [limit, setLimit] = useState(EVIDENCE_FIRST);
  const take = Math.min(limit, EVIDENCE_MAX, g.event_ids.length);
  // newest first: the freshest proof is the most relevant
  const shown = g.event_ids.slice(-take).reverse();
  const more = Math.min(g.event_ids.length, EVIDENCE_MAX) - take;
  const tr = TREND[g.trend];

  return (
    <div className="evidence" id={id} role="region" aria-label={`Messages behind “${g.display}”`}>
      <p className="evidence-meta">
        <strong>
          {g.count} message{g.count === 1 ? "" : "s"} from {g.chatters} chatter
          {g.chatters === 1 ? "" : "s"}
        </strong>{" "}
        · {pct(g.share)} of the window ·{" "}
        {g.last_ts_ms - g.first_ts_ms < 1_000
          ? "all within a second"
          : `spanning ${spanShort(g.last_ts_ms - g.first_ts_ms)}`}
        , latest {agoPhrase(now - g.last_ts_ms)} · {tr.word}
      </p>
      <ol className="evidence-list">
        {shown.map((eid) => {
          const e = events?.get(eid);
          if (!e) return null;
          return (
            <li key={eid} className="ev">
              <span className="ev-time">{ago(now - e.ts_ms)}</span>
              <span className="ev-author">{e.author}</span>
              <span className="ev-text">{e.text}</span>
            </li>
          );
        })}
      </ol>
      <div className="evidence-foot">
        {more > 0 ? (
          <button className="btn-ghost" onClick={() => setLimit((l) => l * 5)}>
            Show {Math.min(more, limit * 4)} more
          </button>
        ) : (
          <span className="evidence-all">
            {g.event_ids.length > EVIDENCE_MAX
              ? `Latest ${EVIDENCE_MAX} of ${g.event_ids.length} shown`
              : "All messages shown"}
          </span>
        )}
        <span className="evidence-hint">Also highlighted in the chat</span>
        <button className="btn-ghost" onClick={onClose}>
          Close
        </button>
      </div>
    </div>
  );
}

function HowItWorks() {
  return (
    <details className="how-grouping">
      <summary>How grouping works</summary>
      <ul>
        <li>
          <strong>Reactions</strong> — laughter (lol, lmao, kekw, xd, haha…) and emote-only
          messages count as one wave.
        </li>
        <li>
          <strong>Variants</strong> — one-word messages starting with the same four letters, once
          there are at least four of them.
        </li>
        <li>
          <strong>Shared word</strong> — messages that share an uncommon word, once three do.
          Common words (“the”, “stream”, “chat”…) never count.
        </li>
        <li>
          Every message is counted once, in one group. A group needs at least {MIN_CHATTERS}{" "}
          different chatters: one person repeating themselves isn't the room.
        </li>
        <li>No AI and no guesses: fixed rules, recounted every ~1.5s over the selected window.</li>
      </ul>
    </details>
  );
}

/**
 * Slide rows to their new place when the ranking changes (or a group opens above them) instead of
 * jumping. Runs after every render; measuring six rows is cheap.
 */
function useReorderMotion() {
  const items = useRef(new Map<string, HTMLLIElement>());
  const tops = useRef(new Map<string, number>());
  useLayoutEffect(() => {
    const still =
      typeof window === "undefined" ||
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    const next = new Map<string, number>();
    items.current.forEach((el, key) => {
      const top = el.offsetTop;
      next.set(key, top);
      const prev = tops.current.get(key);
      if (!still && prev !== undefined && prev !== top && typeof el.animate === "function") {
        el.animate(
          [{ transform: `translateY(${prev - top}px)` }, { transform: "translateY(0)" }],
          { duration: 320, easing: "cubic-bezier(0.2, 0.7, 0.2, 1)" },
        );
      }
    });
    tops.current = next;
  });
  return (key: string) => (el: HTMLLIElement | null) => {
    if (el) items.current.set(key, el);
    else items.current.delete(key);
  };
}

export function ClusterBoard(props: Props) {
  const { groups, selectedKey, onSelect, status, channel, windowMessages, windowMs, onWindow } =
    props;
  const [showAll, setShowAll] = useState(false);
  const maxRows = showAll ? MAX_ROWS_ALL : (props.maxRows ?? 6);
  const rows = groups.slice(0, maxRows);
  const grouped = groups.reduce((s, g) => s + g.count, 0);
  const singletons = Math.max(0, windowMessages - grouped);
  const itemRef = useReorderMotion();
  const buttons = useRef(new Map<string, HTMLButtonElement>());

  const close = (key: string) => {
    onSelect(null);
    buttons.current.get(key)?.focus();
  };

  return (
    <section className="board" aria-label="Audience clusters">
      <header className="board-head">
        <div>
          <h2 className="board-title">What the room is saying</h2>
          <p className="board-sub">
            Grouped from the last <strong>{windowLong(windowMs)}</strong> of chat, recounted every
            ~1.5s.
          </p>
        </div>
        <div className="seg" role="radiogroup" aria-label="Time window">
          {WINDOWS.map((w) => (
            <button
              key={w.ms}
              role="radio"
              aria-checked={w.ms === windowMs}
              className={`seg-btn${w.ms === windowMs ? " seg-on" : ""}`}
              onClick={() => onWindow(w.ms)}
            >
              {w.short}
            </button>
          ))}
        </div>
      </header>

      {rows.length === 0 ? (
        <EmptyState status={status} channel={channel} onTryAnother={props.onTryAnother} />
      ) : (
        <ol className="cluster-list">
          {rows.map((g) => {
            const selected = g.key === selectedKey;
            const rule = RULE_CHIP[g.rule];
            const tr = TREND[g.trend];
            const evId = `evidence-${g.key.replace(/[^a-z0-9]/gi, "_")}`;
            return (
              <li key={g.key} ref={itemRef(g.key)} className="cluster-item">
                <button
                  ref={(el) => {
                    if (el) buttons.current.set(g.key, el);
                    else buttons.current.delete(g.key);
                  }}
                  className={`cluster${selected ? " cluster-sel" : ""}`}
                  onClick={() => onSelect(selected ? null : g.key)}
                  aria-expanded={selected}
                  aria-controls={selected ? evId : undefined}
                >
                  <div className="cluster-count">
                    <span className="cluster-n">{compact(g.count)}</span>
                    <span className={`cluster-trend ${tr.cls}`} title={tr.word}>
                      {tr.mark}
                      <span className="sr-only"> {tr.word}</span>
                    </span>
                  </div>
                  <div className="cluster-main">
                    <div className="cluster-label-row">
                      <span className="cluster-label">{g.display}</span>
                      <span className="cluster-chip" title={rule.hint(g)}>
                        {rule.chip}
                      </span>
                      <span className="cluster-people" title="distinct chatters in this group">
                        {compact(g.chatters)} {g.chatters === 1 ? "person" : "people"}
                      </span>
                    </div>
                    <div className="cluster-samples">
                      <span className="cluster-sample">“{g.samples[0]}”</span>
                    </div>
                  </div>
                  <div className="cluster-bar" aria-hidden="true">
                    <span style={{ width: `${Math.max(4, Math.round(g.share * 100))}%` }} />
                  </div>
                </button>
                {selected && (
                  <Evidence
                    key={g.key}
                    id={evId}
                    g={g}
                    events={props.events}
                    now={props.now}
                    onClose={() => close(g.key)}
                  />
                )}
              </li>
            );
          })}
        </ol>
      )}

      {windowMessages > 0 && (
        <footer className="board-foot">
          <div>
            <strong>{compact(windowMessages)}</strong> messages →{" "}
            <strong>{rows.length}</strong> signal{rows.length === 1 ? "" : "s"} ·{" "}
            {compact(singletons)} ungrouped
            {props.soloMessages > 0 && (
              <span title="Groups that came from one chatter alone are not shown as signals">
                {" "}
                (incl. {compact(props.soloMessages)} one-person repeats)
              </span>
            )}
            {groups.length > rows.length && !showAll && (
              <>
                {" · "}
                <button className="link-inline" onClick={() => setShowAll(true)}>
                  +{groups.length - rows.length} more
                </button>
              </>
            )}
            {showAll && groups.length > (props.maxRows ?? 6) && (
              <>
                {" · "}
                <button className="link-inline" onClick={() => setShowAll(false)}>
                  top {props.maxRows ?? 6} only
                </button>
              </>
            )}
            {props.sampled && (
              <span className="sampled-note">
                {" "}
                · chat outran the buffer, so the oldest part of this window is sampled
              </span>
            )}
          </div>
          <HowItWorks />
        </footer>
      )}
    </section>
  );
}
