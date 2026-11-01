import { describe, expect, it } from "vitest";
import { prepare } from "../../src/semantic/prep";

const p = (t: string) => prepare(t, "jynxzi");

describe("prepare: what gets embedded", () => {
  it("keeps the words of a sentence, ordinary reaction words included", () => {
    expect(p("this game is so boring")).toEqual({ kind: "text", key: "this game is so boring" });
    expect(p("what game is this")).toEqual({ kind: "text", key: "what game is this" });
  });
  it("removes emotes and the streamer's name from a sentence before it is embedded", () => {
    expect(p("that clutch was insane KEKW")).toEqual({ kind: "text", key: "that clutch was insane" });
    expect(p("jynxzi is the goat")).toEqual({ kind: "text", key: "is the goat" });
    expect(p("@someone his mic is muted")).toEqual({ kind: "text", key: "his mic is muted" });
  });
});

describe("prepare: reactions are recognised, never embedded", () => {
  it.each([
    ["KEKW", "laughing"],
    ["ахахахах", "laughing"],
    ["😂😂😂", "laughing"],
    ["LMAO", "laughing"],
    ["Pog Pog", "hype"],
    ["LETS GOOO", "hype"],
    ["rip bro", "sad"],
    ["???", "confused"],
    ["huh", "confused"],
    ["hi chat", "greeting"],
    ["hello everyone", "greeting"],
    ["peepoHey", "greeting"],
    ["L streamer", "loss"],
    ["boring", "bored"],
  ])("%s -> %s", (text, family) => {
    expect(p(text)).toMatchObject({ kind: "reaction", family });
  });
  it("an emote whose meaning is unknown groups only with itself", () => {
    expect(p("catJAM catJAM")).toMatchObject({ kind: "reaction", family: "emote:catjam" });
  });
});

describe("prepare: messages that only count when identical", () => {
  it("bare numbers and the streamer's name alone are low-information", () => {
    expect(p("1")).toMatchObject({ kind: "lowinfo", key: "1" });
    expect(p("100")).toMatchObject({ kind: "lowinfo", key: "100" });
    expect(p("jynxzi").kind).toBe("lowinfo");
  });
  it("commands group by command, links and bots never group", () => {
    expect(p("!discord now")).toEqual({ kind: "command", key: "!discord" });
    expect(p("check https://example.com").kind).toBe("skip");
    expect(prepare("anything at all", "jynxzi", true).kind).toBe("skip");
  });
});

describe("prepare: who a message is addressed to is not what it says", () => {
  const v = (t: string) => prepare(t, "jynxzi", false, { vocatives: true });
  it("leaves chat / chatter out of what is compared", () => {
    expect(v("chat he is cooking")).toEqual({ kind: "text", key: "he is cooking" });
    expect(p("chat he is cooking")).toEqual({ kind: "text", key: "chat he is cooking" });
  });
  it("so a reaction aimed at a chatter is the reaction", () => {
    expect(v("L chatter")).toMatchObject({ kind: "reaction", family: "loss" });
    expect(p("L chatter")).toMatchObject({ kind: "text" });
  });
});

describe("prepare: emotes Twitch itself marked", () => {
  const tagged = (t: string, emotes: string[]) => prepare(t, "jynxzi", false, { emotes: new Set(emotes) });
  it("are left out of a sentence even when they look like words", () => {
    expect(p("NOWAYING this is insane")).toEqual({ kind: "text", key: "nowaying this is insane" });
    expect(tagged("NOWAYING this is insane", ["NOWAYING"])).toEqual({ kind: "text", key: "this is insane" });
  });
  it("alone, group only with the same emote", () => {
    expect(p("Kappa")).toMatchObject({ kind: "text" });
    expect(tagged("Kappa", ["Kappa"])).toMatchObject({ kind: "reaction", family: "emote:kappa" });
  });
});
