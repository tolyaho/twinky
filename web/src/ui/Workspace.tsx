import { useEffect, useRef, useState } from "react";
import { normalizeChannel } from "../twitch/parse";
import { topicsEnabled } from "../semantic/enable";
import { clock } from "./format";
import { ChatFeed } from "./ChatFeed";
import { ClusterBoard } from "./ClusterBoard";
import { offAirMode } from "./derive";
import { Pulse } from "./Pulse";
import { BroadcastPill, StatusBadge } from "./StatusBadge";
import { REPLAY_SPEED, type SessionView, type UiStatus } from "./useSession";

interface Props {
  view: SessionView;
  onSwitch: (channel: string) => void;
  onBack: () => void;
  onReplay: () => void;
  /** The recording is being fetched (a dynamic import); its buttons show progress meanwhile. */
  replayPending: boolean;
}

type Tab = "clusters" | "chat" | "pulse";

/** What the chat column says while it has nothing to show, and whether that is still in progress. */
function feedEmpty(status: UiStatus, offAir: boolean, channel: string): [string, boolean] {
  if (status === "not_found") return [`No chat — Twitch has no channel called #${channel}.`, false];
  if (offAir) return ["No messages. Still listening, in case anyone writes.", false];
  switch (status) {
    case "no_network":
      return ["Waiting for the network to come back…", true];
    case "error":
      return ["Retrying the connection…", true];
    case "closed":
      return ["Disconnected.", false];
    case "ended":
      return ["The replay has finished.", false];
    case "quiet":
      return ["Connected. Nobody has written for a while.", false];
    case "connected":
      return ["Joined. Waiting for the first message…", true];
    case "receiving":
    case "replay":
      return ["Waiting for messages…", true];
    default:
      return ["Connecting to chat…", true];
  }
}

export function Workspace({ view, onSwitch, onBack, onReplay, replayPending }: Props) {
  const [topics] = useState(topicsEnabled); // fixed for the visit, as the session's grouper is
  const [tab, setTab] = useState<Tab>("clusters");
  const [switching, setSwitching] = useState(false);
  const [value, setValue] = useState("");
  const now = view.tick?.serverNow ?? Date.now();
  const selectedLabel = view.groups.find((g) => g.key === view.selectedKey)?.display ?? null;
  const { select, selectedKey } = view;
  const windowMessages = view.tick?.windowMessages ?? 0;
  const offAir = offAirMode(view.status, view.broadcast, windowMessages);
  const [emptyText, waiting] = feedEmpty(view.status, offAir !== "none", view.channel);
  const target = normalizeChannel(value);

  // Escape backs out one level: the channel switcher first, then an open group.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Escape") return;
      if (switching) {
        setSwitching(false);
        setValue("");
      } else if (selectedKey) {
        select(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [switching, selectedKey, select]);

  useEffect(() => {
    const prev = document.title;
    document.title = `${view.source === "replay" ? "Replay · " : ""}#${view.channel} · Twinky`;
    return () => {
      document.title = prev;
    };
  }, [view.channel, view.source]);

  // Screen readers get the top signal when it changes, at most every 10s — never every message.
  const [announce, setAnnounce] = useState("");
  const lastAnnounce = useRef({ label: "", at: 0 });
  const top = view.groups[0];
  useEffect(() => {
    if (!top) return;
    const now = Date.now();
    if (top.display !== lastAnnounce.current.label && now - lastAnnounce.current.at > 10_000) {
      lastAnnounce.current = { label: top.display, at: now };
      setAnnounce(`Top signal: ${top.display}, ${top.count} messages from ${top.chatters} chatters`);
    }
  }, [top]);

  const doSwitch = () => {
    if (!target) return;
    onSwitch(target);
    setSwitching(false);
    setValue("");
  };

  const tryAnother = () => {
    setSwitching(true);
    setTab("clusters");
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
          {view.source === "live" && (
            <BroadcastPill b={view.broadcast} now={Date.now()} channel={view.channel} />
          )}
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
                doSwitch();
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
              <button className="btn-mini" type="submit" disabled={!target}>
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
          <strong>Replay.</strong> A recorded, pseudonymized capture played back at {REPLAY_SPEED}× speed — not a
          live stream. Enter a channel to watch live chat instead.
        </div>
      )}
      {offAir === "banner" && (
        <div className="offair-bar" role="note">
          <strong>#{view.channel} is off air.</strong> Twitch reports no broadcast right now, but
          the chat is still active — what you see below is real, counted as usual.
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
            emptyText={emptyText}
            waiting={waiting}
          />
        </div>

        <div className="zone zone-board">
          <ClusterBoard
            groups={view.groups}
            events={view.tick?.events ?? null}
            now={now}
            selectedKey={view.selectedKey}
            onSelect={view.select}
            status={view.status}
            statusInfo={view.statusInfo}
            broadcast={view.broadcast}
            offAir={offAir}
            channel={view.channel}
            windowMessages={windowMessages}
            windowMs={view.windowMs}
            onWindow={view.setWindowMs}
            sampled={view.tick?.sampled ?? false}
            soloMessages={view.tick?.soloMessages ?? 0}
            semantic={view.tick?.semantic}
            topics={topics}
            onTryAnother={tryAnother}
            onReplay={onReplay}
            onBack={onBack}
            replayPending={replayPending}
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
