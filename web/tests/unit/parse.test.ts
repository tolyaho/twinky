import { describe, expect, it } from "vitest";
import parity from "../fixtures/parity.json";
import { emoteWords, normalizeChannel, parsePrivmsg, withEmotes } from "../../src/twitch/parse";

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

describe("emote tags", () => {
  it("reads names from code-point ranges, so emoji before an emote do not shift it", () => {
    expect(emoteWords("25:0-4,12-16/1902:6-10", "Kappa Keepo Kappa")).toEqual(["Kappa", "Keepo"]);
    expect(emoteWords("25:2-6", "😂 Kappa")).toEqual(["Kappa"]);
  });
  it("ignores an empty or malformed tag, and ranges past the end of the text", () => {
    expect(emoteWords(undefined, "Kappa")).toEqual([]);
    expect(emoteWords("", "Kappa")).toEqual([]);
    expect(emoteWords("25:x-y", "Kappa")).toEqual([]);
    expect(emoteWords("25:0-40", "Kappa")).toEqual([]);
  });
  it("adds them to a row without changing what parsePrivmsg returns", () => {
    const line = "@badge-info=;display-name=Someone;emotes=25:0-4;id=e-1;tmi-sent-ts=1700000000000;user-type= :someone!someone@someone.tmi.twitch.tv PRIVMSG #chan :Kappa hi";
    const row = parsePrivmsg(line)!;
    expect(row).not.toHaveProperty("emotes");
    expect(withEmotes(line, row).emotes).toEqual(["Kappa"]);
    const first = "@emotes=25:0-4;id=e-2;tmi-sent-ts=1700000000000 :a!a@a.tmi.twitch.tv PRIVMSG #chan :Kappa";
    expect(withEmotes(first, parsePrivmsg(first)!).emotes).toEqual(["Kappa"]);
    const none = line.replace("emotes=25:0-4", "emotes=");
    expect(withEmotes(none, parsePrivmsg(none)!)).not.toHaveProperty("emotes");
  });
});
