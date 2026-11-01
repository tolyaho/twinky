import { useLayoutEffect, useMemo, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import type { TickSnapshot } from "../engine/session";
import type { SemanticInfo } from "../semantic/live";
import { compact, spanShort } from "./format";
import { assignSlots, buildTimeline, bucketFor, pickSeries } from "./slices";
import type { GroupView } from "./useSession";

interface Props {
  tick: TickSnapshot | null;
  groups: GroupView[];
  selectedKey: string | null;
  onSelect: (key: string | null) => void;
  windowMs: number;
  semantic?: SemanticInfo;
}

const STRIP_H = 30; // all chat
const PANEL_H = 84; // the leading groups
const GAP = 14;
const PAD_T = 4;
const H = PAD_T + STRIP_H + GAP + PANEL_H + 2;
const PANEL_Y = PAD_T + STRIP_H + GAP;

/** "45–50s ago", "3m 20s–3m 00s ago"; the slice still filling is "last 2s, still counting". */
function sliceLabel(start: number, b: number, to: number, open: boolean): string {
  if (open) return `last ${spanShort(Math.max(1000, to - start))}, still counting`;
  const near = to - start - b;
  const far = to - start;
  return near < 1000 ? `${spanShort(far)} ago – now` : `${spanShort(far)}–${spanShort(near)} ago`;
}

function useWidth<T extends HTMLElement>(fallback: number) {
  const ref = useRef<T>(null);
  const [w, setW] = useState(fallback);
  useLayoutEffect(() => {
    const el = ref.current;
    if (!el) return;
    const read = () => el.clientWidth > 0 && setW(el.clientWidth);
    read();
    if (typeof ResizeObserver === "undefined") return;
    const ro = new ResizeObserver(read);
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

export function Timeline({ tick, groups, selectedKey, onSelect, windowMs, semantic }: Props) {
  const [box, w] = useWidth<HTMLDivElement>(280); // the section is always there, the chart not
  const ref = useRef<HTMLDivElement>(null);
  const [active, setActive] = useState<number | null>(null);
  const slots = useRef(new Map<string, number>());
  const b = bucketFor(windowMs);
  const shown = pickSeries(groups, selectedKey);
  const shownKeys = shown.map((g) => g.key).join("|");

  const tl = useMemo(
    () =>
      tick
        ? buildTimeline({
            events: tick.events,
            windowStart: tick.windowMs[0],
            windowEnd: tick.windowMs[1],
            observedMs: tick.observedMs,
            groups: shown,
            bucketMs: b,
          })
        : null,
    // the drawn groups are fixed by their keys; their members come with the tick
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [tick, shownKeys, b],
  );
  const slotOf = useMemo(() => assignSlots(shown.map((g) => g.key), slots.current), [shownKeys]); // eslint-disable-line react-hooks/exhaustive-deps

  const n = tl?.starts.length ?? 0;
  const hasData = !!tl && tl.total.some((v) => v > 0);
  const at = active !== null && active < n ? active : null;

  if (!tl || !hasData) {
    return (
      <div className="tl" ref={box}>
        <TimelineHead b={b} />
        <p className="tl-empty">Nothing to chart yet — the timeline fills in as messages arrive.</p>
      </div>
    );
  }

  const span = Math.max(1, tl.to - tl.from);
  const x = (t: number) => ((t - tl.from) / span) * w;
  // a slice's point sits in the middle of the time it covers; the open slice's, in the middle of
  // the part that has happened
  const px = (i: number) => {
    const s = tl.starts[i];
    const e = i === n - 1 && tl.open ? tl.to : s + tl.bucketMs;
    return x((s + e) / 2);
  };
  const maxTotal = Math.max(1, ...tl.total);
  const maxSeries = Math.max(1, ...tl.series.flatMap((s) => s.counts));
  const yStrip = (v: number) => PAD_T + STRIP_H - (v / maxTotal) * (STRIP_H - 3);
  const yPanel = (v: number) => PANEL_Y + PANEL_H - (v / maxSeries) * (PANEL_H - 6);
  const done = tl.open ? n - 1 : n; // complete slices
  const path = (vals: number[], y: (v: number) => number, from: number, to: number) =>
    vals
      .slice(from, to)
      .map((v, i) => `${i ? "L" : "M"}${px(from + i).toFixed(1)},${y(v).toFixed(1)}`)
      .join(" ");
  const solid = (vals: number[], y: (v: number) => number) => path(vals, y, 0, done);
  // the slice still filling: a dashed step from the last complete one, so a dip there reads as
  // "not finished", not as chat falling away
  const pending = (vals: number[], y: (v: number) => number) => (tl.open && n >= 2 ? path(vals, y, n - 2, n) : "");
  const area = done
    ? `${path(tl.total, yStrip, 0, done)} L${px(done - 1).toFixed(1)},${PAD_T + STRIP_H} L${px(0).toFixed(1)},${PAD_T + STRIP_H} Z`
    : "";
  const firstOnly = done === 0; // only the slice still filling: shown as hollow points
  const listenedFrom = tl.starts[0] - tl.bucketMs; // earlier than this, nothing was heard
  const lateStart = listenedFrom > tl.from;

  const nearest = (clientX: number) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r || !n) return null;
    const cx = clientX - r.left;
    let best = 0;
    for (let i = 1; i < n; i++) if (Math.abs(px(i) - cx) < Math.abs(px(best) - cx)) best = i;
    return best;
  };
  const onMove = (e: PointerEvent) => setActive(nearest(e.clientX));
  const onKey = (e: KeyboardEvent) => {
    const cur = at ?? n - 1;
    const next =
      e.key === "ArrowLeft" ? Math.max(0, cur - 1)
      : e.key === "ArrowRight" ? Math.min(n - 1, cur + 1)
      : e.key === "Home" ? 0
      : e.key === "End" ? n - 1
      : null;
    if (next === null) {
      if (e.key === "Escape" && at !== null) {
        e.stopPropagation(); // closes the readout, not the open group
        setActive(null);
      }
      return;
    }
    e.preventDefault();
    setActive(next);
  };

  const byKey = new Map(shown.map((g) => [g.key, g]));
  const dim = (key: string) => selectedKey !== null && byKey.has(selectedKey) && key !== selectedKey;
  const tipLeft = at !== null ? Math.min(Math.max(px(at), 70), w - 70) : 0;
  const readout =
    at !== null
      ? [
          sliceLabel(tl.starts[at], tl.bucketMs, tl.to, tl.open && at === n - 1),
          `${tl.total[at]} message${tl.total[at] === 1 ? "" : "s"} in all`,
          ...tl.series.map((s) => `${s.counts[at]} ${byKey.get(s.key)?.display ?? ""}`),
        ].join(", ")
      : "";
  const pendingN = semantic && semantic.state !== "failed" ? semantic.pending : 0;

  return (
    <div className="tl" ref={box}>
      <TimelineHead b={tl.bucketMs} />
      <div
        className="tl-chart"
        ref={ref}
        tabIndex={0}
        role="group"
        aria-label={`Audience timeline: messages per ${tl.bucketMs / 1000} seconds, in all and for the leading groups. Use the arrow keys to read each slice.`}
        onPointerMove={onMove}
        onPointerLeave={() => setActive(null)}
        onFocus={() => setActive((a) => a ?? n - 1)}
        onBlur={() => setActive(null)}
        onKeyDown={onKey}
      >
        <svg width={w} height={H} className="tl-svg" aria-hidden="true">
          <text className="tl-k" x={0} y={PAD_T + 9}>
            all chat
          </text>
          <text className="tl-k tl-max" x={w} y={PAD_T + 9}>
            {compact(maxTotal)}
          </text>
          <line className="tl-base" x1={0} x2={w} y1={PAD_T + STRIP_H + 0.5} y2={PAD_T + STRIP_H + 0.5} />
          <text className="tl-k" x={0} y={PANEL_Y + 9}>
            groups
          </text>
          <text className="tl-k tl-max" x={w} y={PANEL_Y + 9}>
            {compact(maxSeries)}
          </text>
          <line className="tl-base" x1={0} x2={w} y1={PANEL_Y + PANEL_H + 0.5} y2={PANEL_Y + PANEL_H + 0.5} />
          {lateStart && (
            // before this session was listening: unknown, not zero
            <>
              <line className="tl-unknown" x1={0} x2={x(listenedFrom)} y1={PAD_T + STRIP_H - 1} y2={PAD_T + STRIP_H - 1} />
              <line className="tl-unknown" x1={0} x2={x(listenedFrom)} y1={PANEL_Y + PANEL_H - 1} y2={PANEL_Y + PANEL_H - 1} />
              {x(listenedFrom) > 92 && (
                <text className="tl-k tl-unknown-k" x={x(listenedFrom) / 2} y={PANEL_Y + PANEL_H - 8}>
                  not listening yet
                </text>
              )}
            </>
          )}
          <path className="tl-total-area" d={area} />
          <path className="tl-total" d={solid(tl.total, yStrip)} />
          {pending(tl.total, yStrip) && <path className="tl-total tl-open" d={pending(tl.total, yStrip)} />}
          {firstOnly && <circle cx={px(0)} cy={yStrip(tl.total[0])} r={3} className="tl-pt tl-pt-open tl-pt-total" />}
          {groups.length === 0 && (
            <text className="tl-k tl-none" x={w / 2} y={PANEL_Y + PANEL_H / 2 + 4}>
              no groups yet
            </text>
          )}
          {tl.series.map((s) => {
            const slot = slotOf.get(s.key) ?? 0;
            const cls = `tl-line tl-s${slot + 1}${dim(s.key) ? " tl-dim" : ""}${s.key === selectedKey ? " tl-sel" : ""}`;
            const d = solid(s.counts, yPanel);
            const p = pending(s.counts, yPanel);
            const single = (done === 1 && !p) || firstOnly; // one point is a dot, not a line
            return (
              <g key={s.key} className={cls}>
                {d && <path d={d} />}
                {p && <path className="tl-open" d={p} />}
                {single && <circle cx={px(0)} cy={yPanel(s.counts[0])} r={3} className={`tl-pt${firstOnly ? " tl-pt-open" : ""}`} />}
              </g>
            );
          })}
          {at !== null && (
            <g className="tl-cross">
              <line x1={px(at)} x2={px(at)} y1={PAD_T} y2={PANEL_Y + PANEL_H} />
              <circle cx={px(at)} cy={yStrip(tl.total[at])} r={3.5} className="tl-dot tl-dot-total" />
              {tl.series.map((s) => (
                <circle
                  key={s.key}
                  cx={px(at)}
                  cy={yPanel(s.counts[at])}
                  r={4}
                  className={`tl-dot tl-s${(slotOf.get(s.key) ?? 0) + 1}${dim(s.key) ? " tl-dim" : ""}`}
                />
              ))}
            </g>
          )}
          {/* wide, invisible strokes: a line is clicked where it is drawn, not on its 2px */}
          {tl.series.map((s) => (
            <path
              key={s.key}
              className="tl-hit"
              d={path(s.counts, yPanel, 0, n)}
              onClick={() => onSelect(s.key === selectedKey ? null : s.key)}
            />
          ))}
        </svg>
        {at !== null && (
          <div className="tl-tip" style={{ left: tipLeft }} aria-hidden="true">
            <div className="tl-tip-when">{sliceLabel(tl.starts[at], tl.bucketMs, tl.to, tl.open && at === n - 1)}</div>
            <div className="tl-tip-row">
              <strong>{tl.total[at]}</strong>
              <span>all chat</span>
            </div>
            {tl.series.map((s) => (
              <div key={s.key} className="tl-tip-row">
                <i className={`tl-key tl-s${(slotOf.get(s.key) ?? 0) + 1}`} />
                <strong>{s.counts[at]}</strong>
                <span>{byKey.get(s.key)?.display}</span>
              </div>
            ))}
          </div>
        )}
        <div className="sr-only" aria-live="polite">
          {readout}
        </div>
      </div>
      <div className="tl-axis" aria-hidden="true">
        <span>{spanShort(tl.to - tl.from)} ago</span>
        <span>now</span>
      </div>
      {shown.length > 0 && (
        <ul className="tl-legend" aria-label="Groups on the timeline">
          {shown.map((g) => {
            const slot = slotOf.get(g.key) ?? 0;
            const on = g.key === selectedKey;
            return (
              <li key={g.key}>
                <button
                  className={`tl-leg${on ? " tl-leg-on" : ""}${dim(g.key) ? " tl-leg-dim" : ""}`}
                  aria-pressed={on}
                  title={on ? "Close this group on the board" : "Open this group on the board"}
                  onClick={() => onSelect(on ? null : g.key)}
                >
                  <i className={`tl-key tl-s${slot + 1}`} aria-hidden="true" />
                  <span className="tl-leg-label">{g.display}</span>
                  <span className="tl-leg-n">{compact(g.count)}</span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
      <p className="tl-note">
        Each line counts the messages a group holds now, by when they were sent.
        {pendingN > 0 && ` ${compact(pendingN)} newest not read by the topic model yet — lines may still rise at the right.`}
      </p>
    </div>
  );
}

function TimelineHead({ b }: { b: number }) {
  return (
    <div className="tl-head">
      <h3 className="tl-title">Audience timeline</h3>
      <span className="muted-tiny">per {b / 1000}s</span>
    </div>
  );
}
