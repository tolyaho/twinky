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
  /** A known bot account (decided from the login before it is pseudonymised). Browser only. */
  bot?: boolean;
  /** Words Twitch marked as its emotes in this message (IRC `emotes` tag). Browser only. */
  emotes?: string[];
}

export type GroupRule = "reaction" | "prefix" | "token";

/**
 * What the live board can show: the ported rules above, plus the browser's grouping by meaning
 * (src/semantic) — a repeated phrase, a topic (different words, one meaning), a shared question,
 * or single words the model found alike ("words": answers or guesses, too short to be a topic).
 */
export type BoardRule = GroupRule | "phrase" | "topic" | "question" | "words";

/** The part of a group that counting needs, whichever engine produced it. */
export type Counted = Pick<Group, "count" | "event_ids"> & { rule: BoardRule };

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
