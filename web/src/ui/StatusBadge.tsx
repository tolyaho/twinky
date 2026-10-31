import type { SourceInfo } from "../engine/session";
import type { UiStatus } from "./useSession";

interface Props {
  status: UiStatus;
  info?: SourceInfo | null;
}

// tone drives the dot colour / animation; label is deliberately honest about what is known.
const MAP: Record<UiStatus, { label: string; tone: "live" | "warn" | "idle" | "bad" | "replay" }> = {
  idle: { label: "Idle", tone: "idle" },
  connecting: { label: "Connecting", tone: "warn" },
  connected: { label: "Connected", tone: "warn" },
  receiving: { label: "Live chat", tone: "live" },
  quiet: { label: "Quiet", tone: "warn" },
  reconnecting: { label: "Reconnecting", tone: "warn" },
  error: { label: "Connection error", tone: "bad" },
  closed: { label: "Disconnected", tone: "idle" },
  offline: { label: "Offline", tone: "idle" },
  not_found: { label: "Not found", tone: "bad" },
  no_network: { label: "No network", tone: "bad" },
  replay: { label: "Replay", tone: "replay" },
  ended: { label: "Replay ended", tone: "idle" },
};

export function StatusBadge({ status, info }: Props) {
  const m = MAP[status] ?? MAP.idle;
  const label =
    status === "reconnecting" && info?.attempt ? `${m.label} · ${info.attempt}` : m.label;
  const animated = m.tone === "live" || m.tone === "warn" || m.tone === "replay";
  return (
    <span
      className={`badge badge-${m.tone}`}
      title={info?.message ?? undefined}
      role="status"
      aria-live="polite"
    >
      <span className={`dot${animated ? " dot-pulse" : ""}`} aria-hidden="true" />
      {label}
    </span>
  );
}
