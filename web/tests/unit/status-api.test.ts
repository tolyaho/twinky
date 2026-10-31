// @vitest-environment node
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { _resetTokenCache, lookup } from "../../api/twitch-status";

const ENV = { id: "client-id", secret: "client-secret" };
const NOW = 1_800_000_000_000;

type Route = (url: string, init?: RequestInit) => Response | Promise<Response>;

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}

/** Fake Twitch: token endpoint, users and streams, each overridable. */
function twitch(over: { token?: Route; users?: Route; streams?: Route } = {}) {
  const calls: string[] = [];
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    calls.push(url.replace(/\?.*/, ""));
    if (url.startsWith("https://id.twitch.tv/oauth2/token")) {
      return (over.token ?? (() => json({ access_token: "tok", expires_in: 3600 })))(url, init);
    }
    if (url.includes("/helix/users")) {
      return (over.users ?? (() => json({ data: [{ id: "42" }] })))(url, init);
    }
    if (url.includes("/helix/streams")) {
      return (over.streams ?? (() => json({ data: [] })))(url, init);
    }
    throw new Error(`unexpected ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return { calls };
}

beforeEach(() => _resetTokenCache());
afterEach(() => vi.unstubAllGlobals());

describe("twitch-status lookup", () => {
  it("rejects a malformed login without calling Twitch", async () => {
    const { calls } = twitch();
    expect((await lookup("not a name!", ENV)).state).toBe("invalid");
    expect(calls).toHaveLength(0);
  });

  it("says unknown — not offline — when no Twitch app is configured", async () => {
    const { calls } = twitch();
    expect(await lookup("xqc", {})).toEqual({
      state: "unknown",
      configured: false,
      reason: "unconfigured",
    });
    expect(calls).toHaveLength(0);
  });

  it("reports live with when it was checked and when the broadcast started", async () => {
    twitch({ streams: () => json({ data: [{ type: "live", started_at: "2026-10-31T18:00:00Z" }] }) });
    const r = await lookup("xqc", ENV, () => NOW);
    expect(r).toMatchObject({ state: "live", configured: true, checkedAt: NOW });
    expect(r.startedAt).toBe(Date.parse("2026-10-31T18:00:00Z"));
    expect(r.recheckAfterMs).toBeGreaterThan(0);
  });

  it("reports offline for an existing channel with no stream", async () => {
    twitch();
    expect(await lookup("kaicenat", ENV, () => NOW)).toMatchObject({ state: "offline", checkedAt: NOW });
  });

  it("reports not_found only when Helix answers with no such user", async () => {
    twitch({ users: () => json({ data: [] }) });
    expect((await lookup("zzqqnotarealchannel9871", ENV)).state).toBe("not_found");
  });

  it("an upstream error is 'twitch_unavailable', never offline or not_found", async () => {
    twitch({ users: () => json({ message: "boom" }, 503) });
    expect(await lookup("xqc", ENV, () => NOW)).toMatchObject({
      state: "unknown",
      reason: "twitch_unavailable",
    });
  });

  it("a timeout or network failure is also 'twitch_unavailable'", async () => {
    twitch({
      streams: () => {
        throw new DOMException("The operation was aborted due to timeout", "TimeoutError");
      },
    });
    expect(await lookup("xqc", ENV)).toMatchObject({ state: "unknown", reason: "twitch_unavailable" });
  });

  it("a malformed Helix body is not read as 'no such user'", async () => {
    twitch({ users: () => json({ error: "weird" }) });
    expect((await lookup("xqc", ENV)).state).toBe("unknown");
  });

  it("refreshes a revoked token once and carries on", async () => {
    let first = true;
    const { calls } = twitch({
      users: () => {
        if (first) {
          first = false;
          return json({ message: "invalid token" }, 401);
        }
        return json({ data: [{ id: "42" }] });
      },
    });
    expect((await lookup("xqc", ENV)).state).toBe("offline");
    expect(calls.filter((c) => c.includes("oauth2/token"))).toHaveLength(2);
  });

  it("a failing token grant is unavailable, not offline", async () => {
    twitch({ token: () => json({ message: "bad secret" }, 403) });
    expect((await lookup("xqc", ENV)).reason).toBe("twitch_unavailable");
  });
});
