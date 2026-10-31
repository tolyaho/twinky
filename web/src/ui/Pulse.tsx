import type { TickSnapshot } from "../engine/session";
import { Sparkline } from "./Sparkline";
import { compact, pct, perMinute, windowLong, windowShort } from "./format";

interface Props {
  tick: TickSnapshot | null;
  windowMs: number;
}

function Stat({ value, label, sub }: { value: string; label: string; sub?: string }) {
  return (
    <div className="stat">
      <div className="stat-value">{value}</div>
      <div className="stat-label">{label}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export function Pulse({ tick, windowMs }: Props) {
  const p = tick?.pulse;
  const windowMsgs = p?.composition.messages ?? 0;
  const grouped = p ? p.composition.messages - p.composition.singletons : 0;
  const clustered = windowMsgs > 0 ? grouped / windowMsgs : 0;

  return (
    <section className="pulse" aria-label="Live statistics">
      <h2 className="pulse-title">Live pulse</h2>
      <p className="pulse-sub">Measured over the last {windowLong(windowMs)}.</p>

      <div className="stat-grid">
        <Stat value={compact(perMinute(windowMsgs, windowMs))} label="msgs / min" />
        <Stat value={p ? String(p.peak_per_second) : "0"} label="peak / sec" />
        <Stat
          value={compact(p?.unique_chatters ?? 0)}
          label={`chatters (${windowShort(windowMs)})`}
          sub={p?.new_chatters ? `+${compact(p.new_chatters)} new` : undefined}
        />
        <Stat value={pct(clustered)} label="clustered" sub={`${compact(grouped)} of ${compact(windowMsgs)}`} />
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
        <Sparkline data={p?.rate ?? []} />
      </div>

      {p && p.questions.length > 0 && (
        <div className="questions">
          <div className="questions-head">Questions to you</div>
          <ul className="questions-list">
            {p.questions.slice(0, 5).map((q, i) => (
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
