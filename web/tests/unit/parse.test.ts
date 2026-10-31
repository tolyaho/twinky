import { describe, expect, it } from "vitest";
import parity from "../fixtures/parity.json";
import { normalizeChannel, parsePrivmsg } from "../../src/twitch/parse";

const data = parity as unknown as { parse: { in: string; out: unknown }[] };

describe("parsePrivmsg parity with capture.py", () => {
  for (const c of data.parse) {
    it(`parses ${JSON.stringify(c.in.slice(0, 48))}…`, () => {
      // capture.py returns a dict with keys id/ts_ms/login/text/user_type/room_id/reply_to;
      // a dropped line is null. Compare the full shape.
      expect(parsePrivmsg(c.in)).toEqual(c.out);
    });
  }
});

describe("normalizeChannel", () => {
  const ok: [string, string][] = [
    ["xqc", "xqc"],
    ["XQC", "xqc"],
    ["  Hasanabi  ", "hasanabi"],
    ["#stableronaldo", "stableronaldo"],
    ["@Jynxzi", "jynxzi"],
    ["https://www.twitch.tv/hasanabi", "hasanabi"],
    ["twitch.tv/xqc", "xqc"],
    ["https://m.twitch.tv/caseoh_/videos", "caseoh_"],
    ["caseoh_", "caseoh_"],
    ["a".repeat(25), "a".repeat(25)],
  ];
  for (const [input, expected] of ok) {
    it(`accepts ${JSON.stringify(input)} -> ${expected}`, () => {
      expect(normalizeChannel(input)).toBe(expected);
    });
  }

  const bad = [
    "",
    "   ",
    "bad name",
    "has-dash",
    "emoji😀",
    "a".repeat(26),
    "../etc/passwd",
    "javascript:alert(1)",
    "https://evil.com/xqc",
    "name!",
  ];
  for (const input of bad) {
    it(`rejects ${JSON.stringify(input)}`, () => {
      expect(normalizeChannel(input)).toBeNull();
    });
  }
});
