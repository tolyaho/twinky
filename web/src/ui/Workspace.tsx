import { useState } from "react";
import { normalizeChannel } from "../twitch/parse";
import { clock } from "./format";
import { ChatFeed } from "./ChatFeed";
import { ClusterBoard } from "./ClusterBoard";
import { Pulse } from "./Pulse";
import { StatusBadge } from "./StatusBadge";
import type { SessionView } from "./useSession";

interface Props {
  view: SessionView;
  onSwitch: (channel: string) => void;
  onBack: () => void;
}

type Tab = "clusters" | "chat" | "pulse";

export function Workspace({ view, onSwitch, onBack }: Props) {
  const [tab, setTab] = useState<Tab>("clusters");
  const [switching, setSwitching] = useState(false);
  const [value, setValue] = useState("");
  const now = view.tick?.serverNow ?? Date.now();
  const selectedLabel = view.tick?.groups.find((g) => g.key === view.selectedKey)?.label ?? null;

  const doSwitch = (raw: string) => {
    const c = normalizeChannel(raw);
    if (c) {
      onSwitch(c);
      setSwitching(false);
      setValue("");
    }
  };

  return (
    <div className="workspace">
      <header className="ws-head">
        <button className="ws-brand" onClick={onBack} title="Back to start">
          Twinky<span className="wordmark-dot">.</span>
        </button>

        <div className="ws-channel">
          {view.source === "replay" && <span className="src-badge src-replay">REPLAY</span>}
          <span className="ws-channel-name">#{view.channel}</span>
          <StatusBadge status={view.status} info={view.statusInfo} />
        </div>

        <div className="ws-tools">
          <span className="ws-clock" aria-label="session time">
            {clock(view.elapsedMs)}
          </span>
          {switching ? (
            <form
              className="switch-form"
              onSubmit={(e) => {
                e.preventDefault();
                doSwitch(value);
              }}
            >
              <input
                autoFocus
                className="switch-input"
                placeholder="channel…"
                value={value}
                onChange={(e) => setValue(e.target.value)}
                onBlur={() => !value && setSwitching(false)}
                autoCapitalize="none"
                autoCorrect="off"
                spellCheck={false}
                aria-label="Switch to channel"
              />
              <button className="btn-mini" type="submit">
                Go
              </button>
            </form>
          ) : (
            <button className="btn-outline" onClick={() => setSwitching(true)}>
              Switch channel
            </button>
          )}
        </div>
      </header>

      {view.source === "replay" && (
        <div className="replay-bar" role="note">
          <strong>Replay.</strong> A recorded, pseudonymized capture replaying in real time — not a
          live stream. Enter a channel to watch live chat instead.
        </div>
      )}

      <div className="tabbar" role="tablist" aria-label="Views">
        {(["clusters", "chat", "pulse"] as Tab[]).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            className={`tab${tab === t ? " tab-on" : ""}`}
            onClick={() => setTab(t)}
          >
            {t === "clusters" ? "Clusters" : t === "chat" ? "Chat" : "Pulse"}
          </button>
        ))}
      </div>

      <main className="ws-grid" data-tab={tab}>
        <div className="zone zone-chat">
          <div className="zone-head">Live chat</div>
          <ChatFeed
            feed={view.feed}
            now={now}
            highlightIds={view.highlightIds}
            selectedLabel={selectedLabel}
          />
        </div>

        <div className="zone zone-board">
          <ClusterBoard
            groups={view.groups}
            selectedKey={view.selectedKey}
            onSelect={view.select}
            status={view.status}
            channel={view.channel}
            windowMessages={view.tick?.windowMessages ?? 0}
          />
        </div>

        <div className="zone zone-pulse">
          <Pulse tick={view.tick} />
        </div>
      </main>
    </div>
  );
}
