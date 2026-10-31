// Optional authoritative channel status. The live chat demo works with ZERO configuration — the
// browser connects to Twitch IRC directly and infers connected/quiet on its own. When the
// deployment additionally has a Twitch app registered (TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET as
// Vercel env vars), this short request/response function upgrades the status to authoritative
// live / offline / not_found via Helix. No visitor ever needs credentials; secrets stay server-side.
//
// It is a plain request/response function (not a long-lived socket), so it fits Vercel's model
// cleanly. If unconfigured it returns {state:"unknown", configured:false} and the client keeps its
// IRC-only states. Every answer carries `checkedAt` (when Twitch was asked) and `recheckAfterMs`
// (when asking again is worthwhile), so a cached answer is never mistaken for a fresh one.
import type { VercelRequest, VercelResponse } from "@vercel/node";

const CHANNEL_RE = /^[a-z0-9_]{1,25}$/;
const TWITCH_TIMEOUT_MS = 4_000; // a hung upstream must not hold the function open
const CACHE_S = 30; // CDN freshness; matches the client's recheck cadence below
const RECHECK_MS = 60_000;

export type BroadcastState = "live" | "offline" | "not_found" | "unknown";

export interface StatusBody {
  state: BroadcastState | "invalid";
  configured?: boolean;
  /** Why the answer is "unknown", when it is. Never carries provider error text. */
  reason?: "unconfigured" | "twitch_unavailable";
  /** Epoch ms at which Twitch was actually asked. */
  checkedAt?: number;
  /** Epoch ms the broadcast started, when live. */
  startedAt?: number;
  recheckAfterMs?: number;
}

// Warm-instance cache for the app access token (client credentials grant).
let tokenCache: { token: string; expiresAt: number } | null = null;

/** Test seam: forget the cached token. */
export function _resetTokenCache(): void {
  tokenCache = null;
}

const timed = (url: string, init: RequestInit = {}) =>
  fetch(url, { ...init, signal: AbortSignal.timeout(TWITCH_TIMEOUT_MS) });

async function appToken(id: string, secret: string): Promise<string | null> {
  if (tokenCache && tokenCache.expiresAt > Date.now() + 60_000) return tokenCache.token;
  const body = new URLSearchParams({
    client_id: id,
    client_secret: secret,
    grant_type: "client_credentials",
  });
  const r = await timed("https://id.twitch.tv/oauth2/token", { method: "POST", body });
  if (!r.ok) return null;
  const j = (await r.json()) as { access_token?: string; expires_in?: number };
  if (!j.access_token) return null;
  tokenCache = {
    token: j.access_token,
    expiresAt: Date.now() + (j.expires_in ?? 3600) * 1000,
  };
  return j.access_token;
}

/** GET a Helix endpoint; on 401 (token revoked or expired early) refresh the token once. */
async function helix(path: string, id: string, secret: string): Promise<Response | null> {
  for (let attempt = 0; attempt < 2; attempt++) {
    const token = await appToken(id, secret);
    if (!token) return null;
    const r = await timed(`https://api.twitch.tv/helix/${path}`, {
      headers: { "Client-Id": id, Authorization: `Bearer ${token}` },
    });
    if (r.status !== 401) return r;
    tokenCache = null;
  }
  return null;
}

/** The whole lookup, separated from the HTTP plumbing so it can be tested directly. */
export async function lookup(
  login: string,
  env: { id?: string; secret?: string },
  now: () => number = Date.now,
): Promise<StatusBody> {
  if (!CHANNEL_RE.test(login)) return { state: "invalid" };
  if (!env.id || !env.secret) {
    return { state: "unknown", configured: false, reason: "unconfigured" };
  }
  const unavailable: StatusBody = {
    state: "unknown",
    configured: true,
    reason: "twitch_unavailable",
    checkedAt: now(),
    recheckAfterMs: RECHECK_MS,
  };
  try {
    const users = await helix(`users?login=${encodeURIComponent(login)}`, env.id, env.secret);
    if (!users?.ok) return unavailable;
    const uj = (await users.json()) as { data?: { id: string }[] };
    if (!Array.isArray(uj.data)) return unavailable;
    const checkedAt = now();
    if (uj.data.length === 0) {
      return { state: "not_found", configured: true, checkedAt, recheckAfterMs: RECHECK_MS };
    }
    const streams = await helix(
      `streams?user_id=${encodeURIComponent(uj.data[0].id)}`,
      env.id,
      env.secret,
    );
    if (!streams?.ok) return unavailable;
    const sj = (await streams.json()) as { data?: { type: string; started_at?: string }[] };
    if (!Array.isArray(sj.data)) return unavailable;
    const live = sj.data.find((s) => s.type === "live");
    const startedAt = live?.started_at ? Date.parse(live.started_at) : NaN;
    return {
      state: live ? "live" : "offline",
      configured: true,
      checkedAt,
      ...(Number.isFinite(startedAt) ? { startedAt } : {}),
      recheckAfterMs: RECHECK_MS,
    };
  } catch {
    // Timeouts and network errors are "we could not ask", never "offline" or "not found".
    return unavailable;
  }
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
  const raw = Array.isArray(req.query.login) ? req.query.login[0] : req.query.login;
  const body = await lookup((raw ?? "").toLowerCase(), {
    id: process.env.TWITCH_CLIENT_ID,
    secret: process.env.TWITCH_CLIENT_SECRET,
  });
  if (body.state === "invalid") return res.status(400).json(body);
  // Cache real answers briefly at the edge; never cache "we could not ask".
  res.setHeader(
    "Cache-Control",
    body.reason === "twitch_unavailable"
      ? "no-store"
      : `public, max-age=0, s-maxage=${CACHE_S}, stale-while-revalidate=${CACHE_S}`,
  );
  return res.status(200).json(body);
}
