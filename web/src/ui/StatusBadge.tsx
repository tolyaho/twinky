import type { SourceInfo } from "../engine/session";
import type { Broadcast } from "./broadcast";
import type { UiStatus } from "./useSession";

interface Props {
  status: UiStatus;
  info?: SourceInfo | null;
}

type Tone = "live" | "warn" | "idle" | "bad" | "replay";

// The CHAT connection. Deliberately silent on whether the broadcast is live — that is the pill
// below, and only when Twitch itself has said so.
const MAP: Record<UiStatus, { label: string; tone: Tone; busy?: boolean }> = {
  idle: { label: "Idle", tone: "idle" },
  connecting: { label: "Connecting", tone: "warn", busy: true },
  connected: { label: "Connected", tone: "warn" },
  receiving: { label: "Live chat", tone: "live" },
  quiet: { label: "Quiet", tone: "warn" },
  reconnecting: { label: "Reconnecting", tone: "warn", busy: true },
  error: { label: "Connection error", tone: "bad", busy: true },
  closed: { label: "Disconnected", tone: "idle" },
  not_found: { label: "Not found", tone: "bad" },
  no_network: { label: "No network", tone: "bad" },
  replay: { label: "Replay", tone: "replay" },
  ended: { label: "Replay ended", tone: "idle" },
};

export function StatusBadge({ status, info }: Props) {
  const m = MAP[status] ?? MAP.idle;
  let label = m.label;
  if (status === "connecting" && info?.phase === "joining") label = "Joining";
  if (status === "reconnecting" && info?.attempt) label = `${m.label} · ${info.attempt}`;
  // Only states that are still moving pulse. A terminal state (not found, disconnected) is still.
  const pulse = m.busy || m.tone === "live" || m.tone === "replay";
  return (
    <span
      className={`badge badge-${m.tone}`}
      title={info?.message ?? undefined}
      role="status"
      aria-live="polite"
    >
      <span className={`dot${pulse ? " dot-pulse" : ""}`} aria-hidden="true" />
      <span key={label} className="badge-label">
        {label}
      </span>
    </span>
  );
}

function duration(ms: number): string {
  const m = Math.max(0, Math.floor(ms / 60_000));
  if (m < 60) return `${m}m`;
  return `${Math.floor(m / 60)}h ${String(m % 60).padStart(2, "0")}m`;
}

/**
 * Whether the broadcaster is on air, per Twitch's own API. Rendered only for an authoritative
 * answer; when the status is unknown there is no pill rather than a guess.
 */
export function BroadcastPill({ b, now, channel }: { b: Broadcast; now: number; channel: string }) {
  if (b.state !== "live" && b.state !== "offline") return null;
  const checked = b.checkedAt ? Math.max(0, Math.round((now - b.checkedAt) / 1000)) : null;
  const fresh =
    checked === null ? "" : checked < 5 ? " (checked just now)" : ` (checked ${checked}s ago)`;
  const live = b.state === "live";
  return (
    <span
      className={`bc-pill ${live ? "bc-live" : "bc-off"}`}
      title={`Twitch reports #${channel} is ${live ? "broadcasting" : "not broadcasting"}${fresh}`}
    >
      {live ? "On air" : "Off air"}
      {live && b.startedAt ? <span className="bc-dur"> · {duration(now - b.startedAt)}</span> : null}
    </span>
  );
}
