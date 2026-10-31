// Faithful port of `src/ts/ingest/capture.py::parse_privmsg`. Same field semantics:
//   - `id` and `tmi-sent-ts` are required; a line missing either is dropped.
//   - `login` comes from the `display-name` tag, lowercased (never the IRC prefix nick).
//   - `ts_ms` is Twitch's own send time, never local arrival time.
//   - `text` is everything after the message-delimiting ":" in the trailer, CRLF stripped.

export interface ChatRow {
  id: string;
  ts_ms: number;
  login: string;
  text: string;
  user_type: string;
  room_id: string | null;
  reply_to: string | null;
}

/** Parse one IRC line. Returns a row for a well-formed tagged PRIVMSG, otherwise null. */
export function parsePrivmsg(line: string): ChatRow | null {
  if (!line.includes("PRIVMSG") || !line.startsWith("@")) return null;
  const sp = line.indexOf(" ");
  if (sp === -1) return null;

  const tags: Record<string, string> = {};
  for (const t of line.slice(1, sp).split(";")) {
    if (!t) continue;
    const eq = t.indexOf("=");
    if (eq === -1) return null; // mirrors Python's `t.split("=", 1)` raising on no "="
    tags[t.slice(0, eq)] = t.slice(eq + 1);
  }

  const mid = tags["id"];
  const ts = tags["tmi-sent-ts"];
  if (!mid || !ts) return null;
  const tsNum = Number(ts);
  if (!Number.isFinite(tsNum)) return null;

  const rest = line.slice(sp + 1);
  if (!rest.startsWith(":")) return null;
  const body = rest.slice(1);
  const colon = body.indexOf(":");
  if (colon === -1) return null;

  return {
    id: mid,
    ts_ms: tsNum,
    login: (tags["display-name"] ?? "").toLowerCase(),
    text: body.slice(colon + 1).replace(/[\r\n]+$/, ""),
    user_type: tags["user-type"] ?? "",
    room_id: tags["room-id"] ?? null,
    reply_to: tags["reply-parent-msg-id"] || null,
  };
}

const CHANNEL_RE = /^[a-z0-9_]{1,25}$/;

/**
 * Normalize user input to a Twitch login. Accepts a bare username or a twitch.tv URL; rejects
 * anything that is not a valid login. Returns null when the input cannot be a channel — the raw
 * value is never used to build a URL path.
 */
export function normalizeChannel(input: string): string | null {
  let s = (input ?? "").trim();
  if (!s) return null;
  // Accept a pasted channel URL: https://www.twitch.tv/<login>[/...]
  const m = s.match(/^(?:https?:\/\/)?(?:www\.|m\.)?twitch\.tv\/([^/?#\s]+)/i);
  if (m) s = m[1];
  s = s.replace(/^#/, "").replace(/^@/, "").toLowerCase();
  return CHANNEL_RE.test(s) ? s : null;
}
