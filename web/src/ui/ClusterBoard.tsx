import { useLayoutEffect, useRef, useState, type CSSProperties, type KeyboardEvent } from "react";
import type { ChatEvent } from "../cluster/types";
import { MIN_CHATTERS, type SourceInfo } from "../engine/session";
import { BoardState, type BoardActions } from "./BoardState";
import type { Broadcast } from "./broadcast";
import type { OffAir } from "./derive";
import { WINDOWS, ago, agoPhrase, compact, pct, spanShort, windowLong } from "./format";
import { EASE_OUT, Num, motionAllowed } from "./motion";
import { overtakeMargin } from "./order";
import type { GroupView, UiStatus } from "./useSession";

interface Props extends BoardActions {
  groups: GroupView[];
  /** The window's messages by id — the evidence behind each group. */
  events: ReadonlyMap<string, ChatEvent> | null;
  now: number;
  selectedKey: string | null;
  onSelect: (key: string | null) => void;
  status: UiStatus;
  statusInfo: SourceInfo | null;
  broadcast: Broadcast;
  offAir: OffAir;
  channel: string;
  windowMessages: number;
  windowMs: number;
  onWindow: (ms: number) => void;
  sampled: boolean;
  soloMessages: number;
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
  const ref = useRef<HTMLDivElement>(null);
  const take = Math.min(limit, EVIDENCE_MAX, g.event_ids.length);
  // newest first: the freshest proof is the most relevant
  const shown = g.event_ids.slice(-take).reverse();
  const more = Math.min(g.event_ids.length, EVIDENCE_MAX) - take;
  const tr = TREND[g.trend];
  const span = g.last_ts_ms - g.first_ts_ms;

  // Unfold, then bring the group into view. The row stays the anchor: the whole group (row and
  // panel) is scrolled fully into view when it fits, and otherwise its row is put at the top —
  // never the bottom of the panel with the group's own label scrolled away.
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const reveal = () => {
      const item = el.parentElement;
      const list = item?.parentElement;
      if (!item || !list) return;
      const top = item.offsetTop; // the list is the rows' offset parent
      const bottom = top + item.offsetHeight;
      const view = list.clientHeight;
      let to = list.scrollTop;
      if (item.offsetHeight > view || top < to) to = top;
      else if (bottom > to + view) to = bottom - view;
      if (to !== list.scrollTop) list.scrollTo?.({ top: to, behavior: motionAllowed() ? "smooth" : "auto" });
    };
    if (!motionAllowed() || typeof el.animate !== "function") return reveal();
    const h = el.offsetHeight;
    const a = el.animate(
      [
        { height: "0px", opacity: 0 },
        { height: `${h}px`, opacity: 1 },
      ],
      { duration: 240, easing: EASE_OUT },
    );
    a.onfinish = reveal;
    return () => a.cancel();
  }, []);

  return (
    <div className="evidence" id={id} ref={ref} role="region" aria-label={`Messages behind “${g.display}”`}>
      <p className="evidence-meta">
        <strong>
          {g.count} message{g.count === 1 ? "" : "s"} from {g.chatters} chatter
          {g.chatters === 1 ? "" : "s"}
        </strong>{" "}
        · {pct(g.share)} of the window ·{" "}
        {span < 1_000 ? "all within a second" : `spanning ${spanShort(span)}`}, latest{" "}
        {agoPhrase(now - g.last_ts_ms)} · {tr.word}
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
        <li>
          Rows change places only when one group clearly overtakes another (by{" "}
          {overtakeMargin(0)}+ messages, or 10% for big groups), so the board doesn't flicker
          between near-ties. Counts are always exact.
        </li>
        <li>No AI and no guesses: fixed rules, recounted every ~1.5s over the selected window.</li>
      </ul>
    </details>
  );
}

/** The 30s / 1m / 5m selector: a radio group with a sliding thumb and arrow-key support. */
function WindowSelect({ value, onChange }: { value: number; onChange: (ms: number) => void }) {
  const idx = Math.max(0, WINDOWS.findIndex((w) => w.ms === value));
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKey = (e: KeyboardEvent) => {
    const d = e.key === "ArrowRight" || e.key === "ArrowDown" ? 1 : e.key === "ArrowLeft" || e.key === "ArrowUp" ? -1 : 0;
    if (!d) return;
    e.preventDefault();
    const n = (idx + d + WINDOWS.length) % WINDOWS.length;
    onChange(WINDOWS[n].ms);
    refs.current[n]?.focus();
  };
  return (
    <div
      className="seg"
      role="radiogroup"
      aria-label="Time window"
      onKeyDown={onKey}
      style={{ "--seg-i": idx } as CSSProperties}
    >
      <span className="seg-thumb" aria-hidden="true" />
      {WINDOWS.map((w, i) => (
        <button
          key={w.ms}
          ref={(el) => (refs.current[i] = el)}
          role="radio"
          aria-checked={i === idx}
          tabIndex={i === idx ? 0 : -1}
          className={`seg-btn${i === idx ? " seg-on" : ""}`}
          onClick={() => onChange(w.ms)}
        >
          {w.short}
        </button>
      ))}
    </div>
  );
}

interface Ghost {
  g: GroupView;
  top: number;
  height: number;
  id: number;
}
let ghostSeq = 0;

/**
 * Motion for the list: rows slide to their new place when the ranking changes or a group above
 * them closes (FLIP), and a row that leaves the window fades out where it stood instead of
 * vanishing. Opening a group is animated by the panel itself, so it is skipped here.
 */
function useBoardMotion(rows: GroupView[], selectedKey: string | null) {
  const items = useRef(new Map<string, HTMLLIElement>());
  const boxes = useRef(new Map<string, { top: number; height: number }>());
  const prevOrder = useRef("");
  const prevSel = useRef<string | null>(null);
  const prevRows = useRef<GroupView[]>([]);
  const [ghosts, setGhosts] = useState<Ghost[]>([]);

  useLayoutEffect(() => {
    const order = rows.map((r) => r.key).join("|");
    const closing = prevSel.current !== null && selectedKey === null;
    const allowed = motionAllowed();
    const slide = allowed && (order !== prevOrder.current || closing);
    const next = new Map<string, { top: number; height: number }>();
    items.current.forEach((el, key) => {
      const box = { top: el.offsetTop, height: el.offsetHeight };
      next.set(key, box);
      const prev = boxes.current.get(key);
      if (slide && prev && Math.abs(prev.top - box.top) > 1 && typeof el.animate === "function") {
        el.animate(
          [{ transform: `translateY(${prev.top - box.top}px)` }, { transform: "translateY(0)" }],
          { duration: 360, easing: EASE_OUT },
        );
      }
    });
    if (allowed && rows.length > 0) {
      const keys = new Set(rows.map((r) => r.key));
      const born: Ghost[] = [];
      for (const r of prevRows.current) {
        const box = boxes.current.get(r.key);
        if (!keys.has(r.key) && box) born.push({ g: r, ...box, id: ++ghostSeq });
      }
      if (born.length) {
        setGhosts((gs) => [...gs, ...born]);
        window.setTimeout(() => setGhosts((gs) => gs.filter((x) => !born.includes(x))), 340);
      }
    }
    boxes.current = next;
    prevOrder.current = order;
    prevSel.current = selectedKey;
    prevRows.current = rows;
  });

  const itemRef = (key: string) => (el: HTMLLIElement | null) => {
    if (el) items.current.set(key, el);
    else items.current.delete(key);
  };
  return { itemRef, ghosts };
}

function RowBody({ g }: { g: GroupView }) {
  const rule = RULE_CHIP[g.rule];
  const tr = TREND[g.trend];
  return (
    <>
      <div className="cluster-count">
        <Num value={g.count} text={compact(g.count)} className="cluster-n" emphasis={g.surge} />
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
        <span style={{ transform: `scaleX(${Math.max(0.04, Math.min(1, g.share))})` }} />
      </div>
    </>
  );
}

export function ClusterBoard(props: Props) {
  const { groups, selectedKey, onSelect, status, channel, windowMessages, windowMs, onWindow } =
    props;
  const [showAll, setShowAll] = useState(false);
  const maxRows = showAll ? MAX_ROWS_ALL : (props.maxRows ?? 6);
  const rows = groups.slice(0, maxRows);
  const grouped = groups.reduce((s, g) => s + g.count, 0);
  const singletons = Math.max(0, windowMessages - grouped);
  const { itemRef, ghosts } = useBoardMotion(rows, selectedKey);
  const buttons = useRef(new Map<string, HTMLButtonElement>());
  const showBoard = rows.length > 0 && props.offAir !== "screen";

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
            Grouped from the last <strong>{windowLong(windowMs)}</strong> of chat
            <span className="board-sub-extra">, recounted every ~1.5s</span>.
          </p>
        </div>
        <WindowSelect value={windowMs} onChange={onWindow} />
      </header>

      {!showBoard ? (
        <BoardState
          status={status}
          info={props.statusInfo}
          broadcast={props.broadcast}
          offAir={props.offAir}
          channel={channel}
          windowMessages={windowMessages}
          windowMs={windowMs}
          onTryAnother={props.onTryAnother}
          onReplay={props.onReplay}
          onBack={props.onBack}
          replayPending={props.replayPending}
        />
      ) : (
        <ol className="cluster-list">
          {rows.map((g) => {
            const selected = g.key === selectedKey;
            const evId = `evidence-${g.key.replace(/[^a-z0-9]/gi, "_")}`;
            return (
              <li key={g.key} ref={itemRef(g.key)} className="cluster-item">
                <button
                  ref={(el) => {
                    if (el) buttons.current.set(g.key, el);
                    else buttons.current.delete(g.key);
                  }}
                  className={`cluster${selected ? " cluster-sel" : ""}`}
                  data-trend={g.trend}
                  onClick={() => onSelect(selected ? null : g.key)}
                  aria-expanded={selected}
                  aria-controls={selected ? evId : undefined}
                >
                  <RowBody g={g} />
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
          {ghosts.map((x) => (
            <li
              key={`ghost-${x.id}`}
              className="cluster-item cluster-ghost"
              style={{ top: x.top, height: x.height }}
              aria-hidden="true"
            >
              <div className="cluster">
                <RowBody g={x.g} />
              </div>
            </li>
          ))}
        </ol>
      )}

      {windowMessages > 0 && showBoard && (
        <footer className="board-foot">
          <div>
            <Num value={windowMessages} text={compact(windowMessages)} className="foot-n" /> messages →{" "}
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
