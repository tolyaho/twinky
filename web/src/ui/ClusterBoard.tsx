import type { GroupView, UiStatus } from "./useSession";
import { WINDOWS, compact, pct, windowLong } from "./format";

interface Props {
  groups: GroupView[];
  selectedKey: string | null;
  onSelect: (key: string | null) => void;
  status: UiStatus;
  channel: string;
  windowMessages: number;
  windowMs: number;
  onWindow: (ms: number) => void;
  sampled: boolean;
  onTryAnother: () => void;
  maxRows?: number;
}

const RULE_CHIP: Record<GroupView["rule"], { chip: string; hint: string }> = {
  reaction: { chip: "reactions", hint: "laughter & emotes" },
  prefix: { chip: "same word", hint: "same word, many typists" },
  token: { chip: "shared word", hint: "messages sharing a word" },
};

const TREND: Record<GroupView["trend"], { mark: string; cls: string; word: string }> = {
  new: { mark: "●", cls: "t-new", word: "new" },
  up: { mark: "▲", cls: "t-up", word: "growing" },
  flat: { mark: "–", cls: "t-flat", word: "steady" },
  down: { mark: "▼", cls: "t-down", word: "fading" },
};

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
  let body = "Groups appear when several people say the same thing within about a minute.";
  if (status === "connecting") {
    title = `Connecting to #${channel}`;
    body = "Opening an anonymous connection to Twitch chat.";
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
  } else if (status === "error") {
    title = "Connection trouble";
    body = "The connection to Twitch dropped. Reconnecting…";
  } else if (status === "receiving") {
    title = "Chat is flowing";
    body =
      "Nothing has formed a clear group yet — the room is saying lots of different things. Watch this space.";
  }
  return (
    <div className="board-empty">
      <div className="board-empty-title">{title}</div>
      <p className="board-empty-body">{body}</p>
      {(status === "not_found" || status === "offline" || status === "quiet") && (
        <button className="btn-light" onClick={onTryAnother}>
          Try another channel
        </button>
      )}
    </div>
  );
}

export function ClusterBoard(props: Props) {
  const { groups, selectedKey, onSelect, status, channel, windowMessages, windowMs, onWindow } =
    props;
  const maxRows = props.maxRows ?? 6;
  const rows = groups.slice(0, maxRows);
  const grouped = groups.reduce((s, g) => s + g.count, 0);
  const singletons = Math.max(0, windowMessages - grouped);

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
            return (
              <li key={g.key}>
                <button
                  className={`cluster${selected ? " cluster-sel" : ""}`}
                  onClick={() => onSelect(selected ? null : g.key)}
                  aria-expanded={selected}
                >
                  <div className="cluster-count">
                    <span className="cluster-n">{compact(g.count)}</span>
                    <span className={`cluster-trend ${tr.cls}`} title={tr.word}>
                      {tr.mark}
                    </span>
                  </div>
                  <div className="cluster-main">
                    <div className="cluster-label-row">
                      <span className="cluster-label">{g.label}</span>
                      <span className="cluster-chip" title={rule.hint}>
                        {rule.chip}
                      </span>
                      <span className="cluster-people" title="distinct chatters in this group">
                        {compact(g.chatters)} {g.chatters === 1 ? "person" : "people"}
                      </span>
                    </div>
                    <div className="cluster-samples">
                      {(selected ? g.samples : g.samples.slice(0, 1)).map((s, i) => (
                        <span className="cluster-sample" key={i}>
                          “{s}”
                        </span>
                      ))}
                    </div>
                    {selected && (
                      <div className="cluster-detail">
                        <span>
                          {g.count} message{g.count === 1 ? "" : "s"} from {g.chatters}{" "}
                          {g.chatters === 1 ? "chatter" : "chatters"} · {pct(g.share)} of the
                          window · {tr.word}
                        </span>
                        <span className="cluster-detail-hint">highlighted in chat →</span>
                      </div>
                    )}
                  </div>
                  <div className="cluster-bar" aria-hidden="true">
                    <span style={{ width: `${Math.max(4, Math.round(g.share * 100))}%` }} />
                  </div>
                </button>
              </li>
            );
          })}
        </ol>
      )}

      {rows.length > 0 && (
        <footer className="board-foot">
          <strong>{compact(windowMessages)}</strong> messages →{" "}
          <strong>{rows.length}</strong> signal{rows.length === 1 ? "" : "s"} ·{" "}
          {compact(singletons)} ungrouped
          {groups.length > maxRows ? ` · +${groups.length - maxRows} more` : ""}
          {props.sampled && (
            <span className="sampled-note">
              {" "}
              · chat outran the buffer, so the oldest part of this window is sampled
            </span>
          )}
        </footer>
      )}
    </section>
  );
}
