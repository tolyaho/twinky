// Optional authoritative channel status. The live chat demo works with ZERO configuration — the
// browser connects to Twitch IRC directly and infers connected/quiet on its own. When the
// deployment additionally has a Twitch app registered (TWITCH_CLIENT_ID / TWITCH_CLIENT_SECRET as
// Vercel env vars), this short request/response function upgrades the status to authoritative
// live / offline / not_found via Helix. No visitor ever needs credentials; secrets stay server-side.
//
// It is a plain request/response function (not a long-lived socket), so it fits Vercel's model
// cleanly. If unconfigured it returns {state:"unknown"} and the client simply keeps its IRC-only
// states.
import type { VercelRequest, VercelResponse } from "@vercel/node";

const CHANNEL_RE = /^[a-z0-9_]{1,25}$/;

// Warm-instance cache for the app access token (client credentials grant).
let tokenCache: { token: string; expiresAt: number } | null = null;

async function appToken(id: string, secret: string): Promise<string | null> {
  if (tokenCache && tokenCache.expiresAt > Date.now() + 60_000) return tokenCache.token;
  const body = new URLSearchParams({
    client_id: id,
    client_secret: secret,
    grant_type: "client_credentials",
  });
  const r = await fetch("https://id.twitch.tv/oauth2/token", { method: "POST", body });
  if (!r.ok) return null;
  const j = (await r.json()) as { access_token?: string; expires_in?: number };
  if (!j.access_token) return null;
  tokenCache = {
    token: j.access_token,
    expiresAt: Date.now() + (j.expires_in ?? 3600) * 1000,
  };
  return j.access_token;
}

export default async function handler(req: VercelRequest, res: VercelResponse) {
  res.setHeader("Cache-Control", "public, max-age=15, s-maxage=15");

  const raw = Array.isArray(req.query.login) ? req.query.login[0] : req.query.login;
  const login = (raw ?? "").toLowerCase();
  if (!CHANNEL_RE.test(login)) {
    return res.status(400).json({ state: "invalid" });
  }

  const id = process.env.TWITCH_CLIENT_ID;
  const secret = process.env.TWITCH_CLIENT_SECRET;
  if (!id || !secret) {
    // Not configured — the client falls back to IRC-only states. This is a valid 200, not an error.
    return res.status(200).json({ state: "unknown", configured: false });
  }

  try {
    const token = await appToken(id, secret);
    if (!token) return res.status(200).json({ state: "unknown", configured: true });

    const headers = { "Client-Id": id, Authorization: `Bearer ${token}` };
    const users = await fetch(
      `https://api.twitch.tv/helix/users?login=${encodeURIComponent(login)}`,
      { headers },
    );
    if (!users.ok) return res.status(200).json({ state: "unknown", configured: true });
    const uj = (await users.json()) as { data?: { id: string }[] };
    if (!uj.data || uj.data.length === 0) {
      return res.status(200).json({ state: "not_found" });
    }

    const userId = uj.data[0].id;
    const streams = await fetch(
      `https://api.twitch.tv/helix/streams?user_id=${encodeURIComponent(userId)}`,
      { headers },
    );
    if (!streams.ok) return res.status(200).json({ state: "unknown", configured: true });
    const sj = (await streams.json()) as { data?: { type: string }[] };
    const live = Array.isArray(sj.data) && sj.data.length > 0 && sj.data[0].type === "live";
    return res.status(200).json({ state: live ? "live" : "offline" });
  } catch {
    // Never leak provider errors; the client treats "unknown" as "keep the IRC-only states".
    return res.status(200).json({ state: "unknown", configured: true });
  }
}
