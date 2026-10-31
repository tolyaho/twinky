// Client-side pseudonymiser. Mirrors the intent of `capture.py::pseudonym`: a real Twitch login
// never appears in the UI, only a stable per-session handle.
//
// The salt is random per browser session and is never persisted or transmitted, exactly like
// `live_chat.py::_live_salt`. This is a display privacy measure, not a cryptographic anonymity
// guarantee — message *text* is still shown verbatim (it is public chat and may contain names),
// which the privacy note in the UI states plainly.

function cyrb53(str: string, seed = 0): number {
  let h1 = 0xdeadbeef ^ seed;
  let h2 = 0x41c6ce57 ^ seed;
  for (let i = 0; i < str.length; i++) {
    const ch = str.charCodeAt(i);
    h1 = Math.imul(h1 ^ ch, 2654435761);
    h2 = Math.imul(h2 ^ ch, 1597334677);
  }
  h1 = Math.imul(h1 ^ (h1 >>> 16), 2246822507);
  h1 ^= Math.imul(h2 ^ (h2 >>> 13), 3266489909);
  h2 = Math.imul(h2 ^ (h2 >>> 16), 2246822507);
  h2 ^= Math.imul(h1 ^ (h1 >>> 13), 3266489909);
  return 4294967296 * (2097151 & h2) + (h1 >>> 0);
}

function randomSalt(): string {
  const buf = new Uint32Array(4);
  if (typeof crypto !== "undefined" && crypto.getRandomValues) {
    crypto.getRandomValues(buf);
  } else {
    for (let i = 0; i < buf.length; i++) buf[i] = Math.floor(Math.random() * 0xffffffff);
  }
  return Array.from(buf, (n) => n.toString(16).padStart(8, "0")).join("");
}

export class Pseudonymizer {
  private readonly salt: string;
  private readonly cache = new Map<string, string>();

  constructor(salt?: string) {
    this.salt = salt ?? randomSalt();
  }

  /** Stable per-session handle for a login, e.g. "u_3a9f0c21b4". Memoised. */
  label(login: string): string {
    const key = login.toLowerCase();
    let v = this.cache.get(key);
    if (v === undefined) {
      const h = cyrb53(`${this.salt}|${key}`).toString(16).padStart(14, "0");
      v = "u_" + h.slice(0, 10);
      this.cache.set(key, v);
    }
    return v;
  }
}
