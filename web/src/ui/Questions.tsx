import { useMemo, useState } from "react";
import type { ChatEvent } from "../cluster/types";
import { ago, compact, windowLong } from "./format";
import { questionsInChat, type AskedQuestion } from "./asked";
import type { GroupView } from "./useSession";

interface Props {
  groups: GroupView[];
  events: ReadonlyMap<string, ChatEvent> | null;
  now: number;
  /** when this session began listening, in event time: earlier than this nothing is known */
  since: number;
  windowMs: number;
  /** the board groups by meaning (and the model is running), so paraphrases can join */
  byMeaning: boolean;
  selectedKey: string | null;
  onSelect: (key: string | null) => void;
}

const SHOW = 5; // repeated questions listed
const NEW_MS = 20_000; // first asked this recently: marked new

function Question({ q, events, now, since, open, onToggle, selectedKey, onSelect }: {
  q: AskedQuestion;
  events: ReadonlyMap<string, ChatEvent> | null;
  now: number;
  since: number;
  open: boolean;
  onToggle: () => void;
  selectedKey: string | null;
  onSelect: (key: string | null) => void;
}) {
  const messages = q.event_ids.length;
  // new: first asked in the last 20 s, by a session that was already listening 20 s before that
  const fresh = now - q.first_ts_ms < NEW_MS && q.first_ts_ms - since >= NEW_MS;
  const id = `q-${q.key.replace(/[^a-z0-9]/gi, "_")}`;
  return (
    <li className={`q${open ? " q-open" : ""}`}>
      <button className="q-head" aria-expanded={open} aria-controls={open ? id : undefined} onClick={onToggle}>
        <span className="q-text">{q.label}</span>
        <span className="q-meta">
          Asked by <strong>{compact(q.askers)}</strong> chatters
          {messages > q.askers && ` · ${compact(messages)} messages`}
          {fresh && <span className="q-new"> · new</span>}
        </span>
      </button>
      {open && (
        <div className="q-ev" id={id}>
          <ol className="q-ev-list">
            {[...q.event_ids].reverse().map((eid) => {
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
          <div className="q-foot">
            <span className="q-how">
              {q.how === "meaning" ? "Different wordings, grouped by meaning" : "The same wording"}
            </span>
            {q.groupKey && (
              <button
                className="btn-ghost"
                aria-pressed={selectedKey === q.groupKey}
                onClick={() => onSelect(selectedKey === q.groupKey ? null : q.groupKey)}
              >
                {selectedKey === q.groupKey ? "Shown on the board" : "Show on the board"}
              </button>
            )}
          </div>
        </div>
      )}
    </li>
  );
}

export function Questions({ groups, events, now, since, windowMs, byMeaning, selectedKey, onSelect }: Props) {
  const [open, setOpen] = useState<Set<string>>(() => new Set());
  const view = useMemo(
    () => (events ? questionsInChat(groups, events, byMeaning) : { repeated: [], others: [] }),
    [groups, events, byMeaning],
  );
  const toggle = (k: string) =>
    setOpen((s) => {
      const n = new Set(s);
      if (!n.delete(k)) n.add(k);
      return n;
    });
  const { repeated, others } = view;
  if (!events || events.size === 0) return null;

  return (
    <section className="qs" aria-label="Questions in chat">
      <div className="qs-head">
        <h3 className="qs-title">Questions in chat</h3>
        <span className="muted-tiny">{byMeaning ? "by meaning" : "same wording"}</span>
      </div>
      {repeated.length > 0 ? (
        <ul className="qs-list">
          {repeated.slice(0, SHOW).map((q) => (
            <Question
              key={q.key}
              q={q}
              events={events}
              now={now}
              since={since}
              open={open.has(q.key)}
              onToggle={() => toggle(q.key)}
              selectedKey={selectedKey}
              onSelect={onSelect}
            />
          ))}
        </ul>
      ) : (
        <p className="qs-empty">
          {others.length
            ? `No question asked by more than one chatter in the last ${windowLong(windowMs)}.`
            : `No questions in the last ${windowLong(windowMs)}.`}
        </p>
      )}
      {repeated.length > SHOW && <p className="qs-more">+{repeated.length - SHOW} more asked by several chatters</p>}
      {others.length > 0 && (
        <details className="qs-others">
          <summary>
            {compact(others.length)} other question{others.length === 1 ? "" : "s"}, each from one chatter
          </summary>
          <ol className="q-ev-list">
            {others.slice(0, 12).map((o) => (
              <li key={o.id} className="ev">
                <span className="ev-time">{ago(now - o.ts_ms)}</span>
                <span className="ev-author">{o.author}</span>
                <span className="ev-text">
                  {o.text}
                  {o.times > 1 && <span className="q-times"> ×{o.times}</span>}
                </span>
              </li>
            ))}
          </ol>
        </details>
      )}
    </section>
  );
}
