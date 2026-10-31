import { describe, expect, it } from "vitest";
import { UNKNOWN, readStatus, type Broadcast } from "../../src/ui/broadcast";
import { effectiveStatus, offAirMode } from "../../src/ui/derive";

const b = (state: Broadcast["state"]): Broadcast => ({ ...UNKNOWN, state, configured: true });

describe("effectiveStatus", () => {
  it("shows Helix's not_found while chat is still connecting", () => {
    expect(effectiveStatus("connecting", b("not_found"))).toBe("not_found");
  });
  it("never overrules an acknowledged JOIN with not_found", () => {
    for (const irc of ["connected", "receiving", "quiet"] as const) {
      expect(effectiveStatus(irc, b("not_found"))).toBe(irc);
    }
  });
  it("offline and unknown never change the connection status", () => {
    for (const irc of ["connecting", "connected", "receiving", "quiet", "no_network"] as const) {
      expect(effectiveStatus(irc, b("offline"))).toBe(irc);
      expect(effectiveStatus(irc, UNKNOWN)).toBe(irc);
    }
  });
});

describe("offAirMode", () => {
  it("is only ever driven by an authoritative offline", () => {
    for (const s of ["live", "unknown", "not_found"] as const) {
      expect(offAirMode("quiet", b(s), 0)).toBe("none");
    }
  });
  it("silent chat on an offline channel: the off-air state", () => {
    expect(offAirMode("connected", b("offline"), 0)).toBe("screen");
    expect(offAirMode("quiet", b("offline"), 0)).toBe("screen");
  });
  it("an offline broadcaster whose chat is still talking keeps the board, with a banner", () => {
    expect(offAirMode("receiving", b("offline"), 0)).toBe("banner");
    expect(offAirMode("quiet", b("offline"), 12)).toBe("banner");
  });
  it("not_found and replay are never presented as off air", () => {
    expect(offAirMode("not_found", b("offline"), 0)).toBe("none");
    expect(offAirMode("replay", b("offline"), 5)).toBe("none");
  });
});

describe("readStatus", () => {
  it("reads live, offline and not_found as given", () => {
    expect(readStatus({ state: "live", configured: true, checkedAt: 5, startedAt: 1 }).b).toEqual({
      state: "live",
      configured: true,
      checkedAt: 5,
      startedAt: 1,
    });
    expect(readStatus({ state: "offline", configured: true }).b.state).toBe("offline");
    expect(readStatus({ state: "not_found", configured: true }).b.state).toBe("not_found");
  });
  it("anything else is unknown, never a guess", () => {
    expect(readStatus({ state: "probably-offline" }).b.state).toBe("unknown");
    expect(readStatus(null).b.state).toBe("unknown");
  });
  it("stops asking when no Twitch app is configured, and re-asks otherwise", () => {
    expect(readStatus({ state: "unknown", configured: false }).recheckMs).toBeNull();
    expect(readStatus({ state: "live", configured: true, recheckAfterMs: 60_000 }).recheckMs).toBe(60_000);
    expect(readStatus({ state: "unknown", configured: true, recheckAfterMs: 1 }).recheckMs).toBe(250);
  });
  it("drops a startedAt that came without a live state", () => {
    expect(readStatus({ state: "offline", configured: true, startedAt: 9 }).b.startedAt).toBeNull();
  });
});
