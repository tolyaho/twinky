import type { TickSnapshot } from "../engine/session";
import { Questions } from "./Questions";
import { Timeline } from "./Timeline";
import { compact, pct, perMinute, spanLong, windowLong } from "./format";
import { Num } from "./motion";
import type { GroupView } from "./useSession";

interface Props {
  tick: TickSnapshot | null;
  windowMs: number;
  groups: GroupView[];
  selectedKey: string | null;
  onSelect: (key: string | null) => void;
}

const MIN_RATE_SPAN_MS = 5_000; // below this a per-minute rate is mostly noise

function Stat({
  value,
  n,
  label,
  sub,
  title,
}: {
  value: string;
  /** The number behind `value`, so the change rolls in the right direction. */
  n?: number;
  label: string;
  sub?: string;
  title?: string;
}) {
  return (
    <div className="stat" title={title}>
      <div className="stat-value">
        <Num value={n ?? value} text={value} />
      </div>
      <div className="stat-label">{label}</div>
      {sub && <div className="stat-sub">{sub}</div>}
    </div>
  );
}

export function Pulse({ tick, windowMs, groups, selectedKey, onSelect }: Props) {
  const p = tick?.pulse;
  const windowMsgs = p?.composition.messages ?? 0;
  const grouped = p ? p.composition.messages - p.composition.singletons : 0;
  const clustered = windowMsgs > 0 ? grouped / windowMsgs : 0;
  // Until the session is older than the window, the window is partly time we were not listening.
  // Rates divide by the time actually observed, and "new chatters" is withheld: everyone would be
  // "new" simply because we just arrived.
  const observed = tick?.observedMs ?? 0;
  const warm = tick?.warm ?? false;
  const perMin = observed >= MIN_RATE_SPAN_MS ? perMinute(windowMsgs, observed) : null;
  const rate = perMin === null ? "—" : compact(perMin);
  const semantic = tick?.semantic;
  // paraphrased questions join only when the model is actually grouping
  const byMeaning = semantic?.state === "ready" || semantic?.state === "loading";

  return (
    <section className="pulse" aria-label="Live statistics">
      <h2 className="pulse-title">Live pulse</h2>
      <p className="pulse-sub">
        Measured over the last {windowLong(windowMs)}
        {tick && !warm
          ? ` — so far the ${spanLong(Math.max(observed, 1000))} since you connected.`
          : "."}
      </p>

      <div className="stat-grid stat-row">
        <Stat value={rate} n={perMin ?? undefined} label="msgs / min" title="Messages in the window ÷ time observed" />
        <Stat
          value={compact(p?.unique_chatters ?? 0)}
          n={p?.unique_chatters ?? 0}
          label="chatters"
          sub={warm && p?.new_chatters ? `+${compact(p.new_chatters)} new` : undefined}
          title="Distinct chatters who wrote in the window. Not viewers: most viewers never type."
        />
        <Stat
          value={p ? String(p.peak_per_second) : "0"}
          n={p?.peak_per_second ?? 0}
          label="peak / sec"
          title="Busiest 10-second stretch, per second"
        />
      </div>

      <Timeline
        tick={tick}
        groups={groups}
        selectedKey={selectedKey}
        onSelect={onSelect}
        windowMs={windowMs}
        semantic={semantic}
      />

      <Questions
        groups={groups}
        events={tick?.events ?? null}
        now={tick?.serverNow ?? 0}
        since={tick ? tick.windowMs[1] - tick.observedMs : 0}
        windowMs={windowMs}
        byMeaning={byMeaning}
        selectedKey={selectedKey}
        onSelect={onSelect}
      />

      {/* how the grouping itself is doing: worth a look, not worth the space above */}
      <details className="pulse-more">
        <summary>More numbers</summary>
        <div className="stat-grid">
          <Stat
            value={pct(clustered)}
            n={clustered}
            label="in a group"
            sub={`${compact(grouped)} of ${compact(windowMsgs)}`}
            title="Share of the window's messages that landed in a group"
          />
          <Stat value={compact(p?.active_groups ?? 0)} n={p?.active_groups ?? 0} label="groups" />
          <Stat
            value={p?.reaction_wave ? compact(p.reaction_wave) : "—"}
            n={p?.reaction_wave || undefined}
            label="reactions"
            sub={p?.reaction_wave ? "laughs & emotes" : undefined}
            title="Messages in reaction groups"
          />
          <Stat
            value={p ? String(p.messages_per_chatter) : "—"}
            n={p?.messages_per_chatter}
            label="msgs / chatter"
            title="How much the average chatter wrote in the window"
          />
        </div>
      </details>
    </section>
  );
}
