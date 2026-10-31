// How the two independent facts — the chat connection (IRC) and the broadcast (Helix, optional) —
// combine into what the page shows. Kept pure so every combination is tested.
import type { SourceState } from "../engine/session";
import type { Broadcast } from "./broadcast";

/**
 * The connection status to show. An authoritative "no such user" from Helix answers sooner than
 * the 8s JOIN timeout, so it is shown while chat is still connecting. Chat traffic outranks it:
 * once Twitch has acknowledged the JOIN, the room exists, whatever the user lookup said.
 */
export function effectiveStatus(irc: SourceState, b: Broadcast): SourceState {
  if (b.state === "not_found" && (irc === "idle" || irc === "connecting" || irc === "reconnecting")) {
    return "not_found";
  }
  return irc;
}

/**
 * How an authoritative "offline" is presented. A broadcaster can be off air while their chat is
 * still talking — that is real chat, and it keeps being read, with a banner. Only when chat is
 * silent too does the board give way to the off-air state.
 */
export type OffAir = "none" | "banner" | "screen";

export function offAirMode(irc: SourceState, b: Broadcast, windowMessages: number): OffAir {
  if (b.state !== "offline") return "none";
  if (irc === "not_found" || irc === "replay" || irc === "ended") return "none";
  return windowMessages > 0 || irc === "receiving" ? "banner" : "screen";
}
