// The chat-only event contract, mirroring the fields `src/ts/events.py` exposes for a
// `chat_message`. The browser demo never sees transcript or frame events (Tier 0 is chat-only),
// so the type is deliberately smaller than the Python `Event`.
export interface ChatEvent {
  /** Twitch's own message id (`id` IRC tag). Stable, used for dedupe and highlighting. */
  id: string;
  /** Twitch's own send timestamp (`tmi-sent-ts`), epoch ms. Never local arrival time. */
  ts_ms: number;
  /** Pseudonymised author. A real login never reaches this field. */
  author: string;
  /** Verbatim message text. */
  text: string;
}

export type GroupRule = "reaction" | "prefix" | "token";

/** One audience signal: a set of messages saying the same thing. Mirrors `reduce.Group`. */
export interface Group {
  key: string;
  rule: GroupRule;
  label: string;
  count: number;
  first_ts_ms: number;
  last_ts_ms: number;
  event_ids: string[];
  samples: string[];
}

export interface GroupedSummary {
  messages: number;
  groups: number;
  grouped: number;
  ungrouped: number;
}
