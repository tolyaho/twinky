import { canonical } from "../cluster/canonical";
import type { QuestionRow } from "../cluster/pulse";
import type { TickSnapshot } from "../engine/session";
import { Sparkline } from "./Sparkline";
import { compact, pct, perMinute, spanLong, windowLong } from "./format";

interface Props {
  tick: TickSnapshot | null;
  windowMs: number;
}

const RATE_BUCKET_MS = 10_000; // matches pulse.ts
const MIN_RATE_SPAN_MS = 5_000; // below this a per-minute rate is mostly noise

function Stat({
  value,
  label,
  sub,
  title,
}: {
  value: string;
  label: string;
  sub?: string;
  title?: string;
}) {
  return (
    <div className="stat" title={title}>
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

/**
 * The ported `questions` rule groups by the chat rules, which never join two identical multi-word
 * messages (a shared word needs three). On screen the same question twice reads as a bug, so
 * rows with the same canonical text are shown once with their counts summed. Display only.
 */
export function mergeQuestions(rows: QuestionRow[]): QuestionRow[] {
  const byText = new Map<string, QuestionRow>();
  for (const q of rows) {
    const k = canonical(q.text) || q.text;
    const had = byText.get(k);
    if (had) byText.set(k, { ...had, count: had.count + q.count, event_ids: [...had.event_ids, ...q.event_ids] });
    else byText.set(k, q);
  }
  // stable re-rank: more askers first, then earliest — the same order the rule itself uses
  return [...byText.values()].sort((a, b) => b.count - a.count || a.ts_ms - b.ts_ms);
}

export function Pulse({ tick, windowMs }: Props) {
  const p = tick?.pulse;
  const windowMsgs = p?.composition.messages ?? 0;
  const grouped = p ? p.composition.messages - p.composition.singletons : 0;
  const clustered = windowMsgs > 0 ? grouped / windowMsgs : 0;
  // Until the session is older than the window, the window is partly time we were not listening.
  // Rates divide by the time actually observed, and "new chatters" is withheld: everyone would be
  // "new" simply because we just arrived.
  const observed = tick?.observedMs ?? 0;
  const warm = tick?.warm ?? false;
  const rate = observed >= MIN_RATE_SPAN_MS ? compact(perMinute(windowMsgs, observed)) : "—";
  const rateFrom =
    tick && !warm
      ? Math.max(0, Math.floor((tick.windowMs[1] - observed - tick.windowMs[0]) / RATE_BUCKET_MS))
      : 0;

  return (
    <section className="pulse" aria-label="Live statistics">
      <h2 className="pulse-title">Live pulse</h2>
      <p className="pulse-sub">
        Measured over the last {windowLong(windowMs)}
        {tick && !warm
          ? ` — so far the ${spanLong(Math.max(observed, 1000))} since you connected.`
          : "."}
      </p>

      <div className="stat-grid">
        <Stat value={rate} label="msgs / min" title="Messages in the window ÷ time observed" />
        <Stat
          value={p ? String(p.peak_per_second) : "0"}
          label="peak / sec"
          title="Busiest 10-second stretch, per second"
        />
        <Stat
          value={compact(p?.unique_chatters ?? 0)}
          label="chatters"
          sub={warm && p?.new_chatters ? `+${compact(p.new_chatters)} new` : undefined}
          title="Distinct chatters who wrote in the window. Not viewers: most viewers never type."
        />
        <Stat
          value={pct(clustered)}
          label="clustered"
          sub={`${compact(grouped)} of ${compact(windowMsgs)}`}
          title="Share of the window's messages that landed in a group"
        />
        <Stat value={compact(p?.active_groups ?? 0)} label="active groups" />
        <Stat
          value={p?.reaction_wave ? compact(p.reaction_wave) : "—"}
          label="reaction wave"
          sub={p?.reaction_wave ? "laughs & emotes" : undefined}
        />
      </div>

      <div className="pulse-spark">
        <div className="pulse-spark-head">
          <span>message rate</span>
          <span className="muted-tiny">10s buckets</span>
        </div>
        <Sparkline data={p?.rate ?? []} from={rateFrom} />
      </div>

      {p && p.questions.length > 0 && (
        <div className="questions">
          <div className="questions-head">Questions in chat</div>
          <ul className="questions-list">
            {mergeQuestions(p.questions).slice(0, 5).map((q, i) => (
              <li key={i} className="question">
                <span className="question-text">{q.text}</span>
                {q.count > 1 && <span className="question-count">×{q.count}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
