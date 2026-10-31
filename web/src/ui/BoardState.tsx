// What the board shows when there are no groups to show — every state distinct, every one honest
// about what is known. Progress is driven by real connection events, never by a timer.
import type { ReactNode } from "react";
import type { SourceInfo } from "../engine/session";
import type { Broadcast } from "./broadcast";
import type { OffAir } from "./derive";
import { compact, windowLong } from "./format";
import type { UiStatus } from "./useSession";

export interface BoardActions {
  onTryAnother: () => void;
  onReplay: () => void;
  onBack: () => void;
  /** The recording is loading after a click on "Watch the recorded demo". */
  replayPending?: boolean;
}

interface Props extends BoardActions {
  status: UiStatus;
  info: SourceInfo | null;
  broadcast: Broadcast;
  offAir: OffAir;
  channel: string;
  windowMessages: number;
  windowMs: number;
}

type Step = "done" | "active" | "todo";

function Steps({ status, info, channel }: { status: UiStatus; info: SourceInfo | null; channel: string }) {
  const joined = status === "connected" || status === "quiet";
  const joining = info?.phase === "joining";
  const s: Step[] = joined
    ? ["done", "done", "active"]
    : joining
      ? ["done", "active", "todo"]
      : ["active", "todo", "todo"];
  const labels = ["Reach Twitch chat", `Join #${channel}`, "Wait for the first messages"];
  return (
    <ol className="steps" aria-label="Connection progress">
      {labels.map((l, i) => (
        <li key={l} className={`step step-${s[i]}`} aria-current={s[i] === "active" ? "step" : undefined}>
          <span className="step-mark" aria-hidden="true" />
          <span className="step-label">{l}</span>
          <span className="sr-only">{s[i] === "done" ? " — done" : s[i] === "active" ? " — in progress" : ""}</span>
        </li>
      ))}
    </ol>
  );
}

function OffAirGlyph() {
  // a broadcast mark whose waves have gone quiet — restrained, no alarm colours
  return (
    <svg className="state-glyph" viewBox="0 0 48 48" aria-hidden="true">
      <circle cx="24" cy="26" r="3.2" />
      <path d="M16.5 18.5a10.6 10.6 0 0 0 0 15" />
      <path d="M31.5 18.5a10.6 10.6 0 0 1 0 15" />
      <path className="faint" d="M11 13a18.4 18.4 0 0 0 0 26" />
      <path className="faint" d="M37 13a18.4 18.4 0 0 1 0 26" />
    </svg>
  );
}

function Actions({
  primary,
  replay,
  back,
  a,
}: {
  primary?: boolean;
  replay?: boolean;
  back?: boolean;
  a: BoardActions;
}) {
  return (
    <div className="state-actions">
      {primary && (
        <button className="btn-light" onClick={a.onTryAnother}>
          Try another channel
        </button>
      )}
      {replay && (
        <button
          className="btn-ghost btn-ghost-lg"
          onClick={a.onReplay}
          disabled={a.replayPending}
          aria-busy={a.replayPending || undefined}
        >
          {a.replayPending && <span className="spinner" aria-hidden="true" />}
          {a.replayPending ? "Loading the recording…" : "Watch the recorded demo"}
          <span className="tag-replay">Replay</span>
        </button>
      )}
      {back && (
        <button className="link-inline" onClick={a.onBack}>
          Back to start
        </button>
      )}
    </div>
  );
}

function State({
  title,
  children,
  busy,
  glyph,
  tone,
}: {
  title: string;
  children: ReactNode;
  busy?: boolean;
  glyph?: ReactNode;
  tone?: "calm" | "bad";
}) {
  return (
    // The live region stays mounted so screen readers hear each change; the content inside is
    // keyed by its title, so a new state arrives with its own entrance.
    <div className={`board-empty${tone ? ` board-empty-${tone}` : ""}`} role="status" aria-live="polite">
      <div key={title} className="board-empty-inner">
        {glyph}
        <div className="board-empty-title">
          {busy && <span className="listening" aria-hidden="true" />}
          {title}
        </div>
        {children}
      </div>
    </div>
  );
}

export function BoardState(p: Props) {
  const { status, info, broadcast, offAir, channel } = p;
  const a: BoardActions = p;

  if (status === "not_found") {
    return (
      <State title="No such channel" tone="bad">
        <p className="board-empty-body">
          Twitch didn't recognise “{channel}” — it doesn't exist or has been suspended. Check the
          spelling and try another.
        </p>
        <Actions primary back a={a} />
      </State>
    );
  }
  if (offAir === "screen") {
    return (
      <State title={`#${channel} is off air`} glyph={<OffAirGlyph />} tone="calm">
        <p className="board-empty-body">
          Twitch reports that #{channel} isn't broadcasting right now. Twinky stays connected to
          the chat, so if anyone talks it will show up here.
        </p>
        <Actions primary replay back a={a} />
      </State>
    );
  }
  if (status === "no_network") {
    return (
      <State title="You're offline" busy>
        <p className="board-empty-body">
          Your device lost its network connection. Twinky reconnects by itself as soon as it's
          back — there is nothing to do.
        </p>
      </State>
    );
  }
  if (status === "error") {
    return (
      <State title="Couldn't reach Twitch" busy>
        <p className="board-empty-body">
          The connection failed. Retrying with a short backoff
          {info?.attempt ? ` (attempt ${info.attempt})` : ""}…
        </p>
      </State>
    );
  }
  if (status === "closed") {
    return (
      <State title="Disconnected">
        <p className="board-empty-body">This session has ended.</p>
        <Actions primary back a={a} />
      </State>
    );
  }
  if (status === "ended") {
    return (
      <State title="Replay finished">
        <p className="board-empty-body">The recorded example has played through.</p>
        <Actions primary back a={a} />
      </State>
    );
  }
  if (status === "connecting" || status === "reconnecting" || status === "connected" || status === "idle") {
    return (
      <State
        title={
          status === "reconnecting"
            ? `Reconnecting to #${channel}`
            : status === "connected"
              ? `Connected to #${channel}`
              : `Connecting to #${channel}`
        }
      >
        <Steps status={status} info={info} channel={channel} />
        <p className="board-empty-body board-empty-hint">
          Anonymous and read-only — your browser talks to Twitch directly.
        </p>
      </State>
    );
  }
  if (status === "quiet") {
    if (broadcast.state === "live") {
      return (
        <State title="On air, but chat is quiet" busy>
          <p className="board-empty-body">
            #{channel} is broadcasting and nobody has written in a while. Groups appear as soon as
            people start repeating themselves.
          </p>
        </State>
      );
    }
    return (
      <State title={`#${channel} is quiet`}>
        <p className="board-empty-body">
          Connected, but no messages for a while. Twinky reads chat and can't see the stream
          itself, so it can't tell whether #{channel} is offline or chat is just slow.
        </p>
        <Actions primary replay back a={a} />
      </State>
    );
  }
  // receiving (or replaying) with nothing grouped yet
  return (
    <State title={`Nothing recurring in the last ${windowLong(p.windowMs)} yet`} busy>
      <p className="board-empty-body">
        {p.windowMessages > 0 ? (
          <>
            <strong>{compact(p.windowMessages)}</strong> message{p.windowMessages === 1 ? "" : "s"}{" "}
            read so far, all saying different things.{" "}
          </>
        ) : null}
        A group appears when at least two people say the same thing.
      </p>
    </State>
  );
}
