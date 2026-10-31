import { useEffect, useRef, useState } from "react";
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

  // Screen readers get the top signal when it changes, at most every 10s — never every message.
  const [announce, setAnnounce] = useState("");
  const lastAnnounce = useRef({ label: "", at: 0 });
  const top = view.groups[0];
  useEffect(() => {
    if (!top) return;
    const now = Date.now();
    if (top.label !== lastAnnounce.current.label && now - lastAnnounce.current.at > 10_000) {
      lastAnnounce.current = { label: top.label, at: now };
      setAnnounce(`Top signal: ${top.label}, ${top.count} messages from ${top.chatters} chatters`);
    }
  }, [top]);

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
            emptyText={
              view.status === "not_found"
                ? "No chat — this channel wasn't found."
                : view.status === "offline"
                  ? "No chat — the channel is offline."
                  : view.status === "quiet" || view.status === "connected"
                    ? "Connected. No messages yet."
                    : "Connecting to chat…"
            }
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
            windowMs={view.windowMs}
            onWindow={view.setWindowMs}
            sampled={view.tick?.sampled ?? false}
            onTryAnother={() => setSwitching(true)}
          />
        </div>

        <div className="zone zone-pulse">
          <Pulse tick={view.tick} windowMs={view.windowMs} />
        </div>
      </main>
      <div className="sr-only" aria-live="polite" aria-atomic="true">
        {announce}
      </div>
    </div>
  );
}
