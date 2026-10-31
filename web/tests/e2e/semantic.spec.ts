import { existsSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { test, expect, served, type Page, type WebSocketRoute } from "./fixtures";

// Grouping by meaning in the real page: the real worker, the real model (served from disk by the
// fixture when it is there), and Twitch chat from a Playwright-mocked socket (TEST FIXTURES ONLY).
// The wordings below were checked against the shipped configuration before being written here:
// the four "no audio" wordings are one topic, the three "mic muted" ones another, the four "what
// game" ones a question; "we cant hear him" joins neither (the grouping does not chain).

let seq = 0;
function line(channel: string, text: string): string {
  const ts = Date.now();
  const n = ++seq;
  const who = `Viewer${n}`;
  return (
    `@display-name=${who};id=sem-${n}-${ts};room-id=1;tmi-sent-ts=${ts};user-type= ` +
    `:${who.toLowerCase()}!u@u.tmi.twitch.tv PRIVMSG #${channel} :${text}`
  );
}

type Sock = { ws: WebSocketRoute; ch: string };
async function mockTwitch(page: Page, onJoin: (s: Sock) => void = () => {}) {
  await page.routeWebSocket(/irc-ws\.chat\.twitch\.tv/, (ws) => {
    ws.onMessage((msg) => {
      const s = typeof msg === "string" ? msg : msg.toString();
      if (s.startsWith("PING")) ws.send(":tmi.twitch.tv PONG tmi.twitch.tv :twinky");
      const m = /^JOIN #(\w+)/.exec(s);
      if (m) {
        ws.send(`@room-id=1 :tmi.twitch.tv ROOMSTATE #${m[1]}`);
        onJoin({ ws, ch: m[1] });
      }
    });
  });
}
const say = (s: Sock, texts: string[]) => texts.forEach((t) => s.ws.send(line(s.ch, t)));

async function enter(page: Page, channel: string) {
  await page.getByPlaceholder("enter a twitch channel").fill(channel);
  await page.getByRole("button", { name: "Watch live" }).click();
  await expect(page.locator(".ws-channel-name")).toHaveText(`#${channel}`);
}

const NO_AUDIO = ["no audio", "audio is gone", "cant hear anything", "no sound"];
const MUTED = ["his mic is muted", "his mic is off", "mic muted?"];
const WHAT_GAME = ["what game is this", "whats this game called", "game name?", "what is this game"];

const row = (page: Page, chip: string) =>
  page.locator(".cluster", { has: page.locator(".cluster-chip", { hasText: new RegExp(`^${chip}$`) }) });
const status = (page: Page) => page.locator(".topic-status");
const MODEL_ON_DISK = existsSync(
  fileURLToPath(new URL("../../eval/.models/Xenova/all-MiniLM-L6-v2/onnx/model_quantized.onnx", import.meta.url)),
);

test.describe("while the model loads", () => {
  test.use({ topicModelDelayMs: 2_500 });

  test("reactions and repeats show at once; topics follow when the model is ready", async ({ page }) => {
    let sock: Sock | null = null;
    await mockTwitch(page, (s) => (sock = s));
    await page.goto("/");
    await enter(page, "semantic");
    await expect.poll(() => sock !== null).toBe(true);
    say(sock!, ["LUL", "KEKW", "LUL", "clip it", "clip it", ...NO_AUDIO, ...MUTED, "we cant hear him"]);

    // before the model: the deterministic groups, and an honest status
    await expect(status(page)).toHaveText("Finding topics…");
    await expect(row(page, "reaction").locator(".cluster-label")).toHaveText("Chat is laughing");
    await expect(row(page, "repeated").locator(".cluster-label")).toHaveText("clip it");
    await expect(row(page, "topic")).toHaveCount(0);
    const head = () => page.locator(".board-head").evaluate((e) => e.getBoundingClientRect().height);
    const loadingHeight = await head();

    // the model: different words, one meaning
    await expect(row(page, "topic")).toHaveCount(2, { timeout: 20_000 });
    await expect(status(page)).toHaveCount(0); // caught up: nothing left unread
    expect(await head()).toBe(loadingHeight); // the status line comes and goes without moving the board
    const counts = await row(page, "topic").locator(".cluster-n").allTextContents();
    expect(counts.sort()).toEqual(["3", "4"]);
    const audio = row(page, "topic").filter({ has: page.locator(".cluster-n", { hasText: /^4$/ }) });
    expect(NO_AUDIO).toContain(await audio.locator(".cluster-label").textContent());

    // the evidence is the messages themselves, in their own words
    await audio.click();
    const evidence = await page.locator(".evidence .ev").allTextContents();
    for (const t of NO_AUDIO) expect(evidence.some((e) => e.includes(t))).toBe(true);
    expect(evidence.some((e) => e.includes("we cant hear him"))).toBe(false);

    if (MODEL_ON_DISK) expect(served).toContain("Xenova/all-MiniLM-L6-v2/onnx/model_quantized.onnx");
  });
});

test("the landing page loads no model and no worker: a crawler costs nothing", async ({ page, context }) => {
  const loaded: string[] = [];
  context.on("request", (r) => /huggingface\.co|cdn\.jsdelivr\.net|\/worker-[\w-]+\.js/.test(r.url()) && loaded.push(r.url()));
  await page.goto("/");
  await expect(page.getByPlaceholder("enter a twitch channel")).toBeVisible();
  await page.waitForTimeout(3_000);
  expect(loaded).toEqual([]);
});

test("a shared question is marked as one", async ({ page }) => {
  let sock: Sock | null = null;
  await mockTwitch(page, (s) => (sock = s));
  await page.goto("/");
  await enter(page, "questions");
  await expect.poll(() => sock !== null).toBe(true);
  say(sock!, WHAT_GAME);
  await expect(row(page, "question")).toHaveCount(1, { timeout: 20_000 });
  await expect(row(page, "question").locator(".cluster-n")).toHaveText("4");
});

test("?topics=off keeps the word rules for the whole visit, and never fetches a model", async ({ page, context }) => {
  const modelRequests: string[] = [];
  context.on("request", (r) => /huggingface\.co|cdn\.jsdelivr\.net/.test(r.url()) && modelRequests.push(r.url()));
  let sock: Sock | null = null;
  await mockTwitch(page, (s) => (sock = s));
  await page.goto("/?topics=off");
  await enter(page, "baseline");
  await expect(page).toHaveURL(/\?channel=baseline&topics=off$/);
  await expect.poll(() => sock !== null).toBe(true);
  say(sock!, ["LMAO", "KEKW", "LMAO", "the boss fight is so hard", "boss is unbeatable", "that boss though", ...NO_AUDIO]);
  await expect(row(page, "shared word").locator(".cluster-label")).toHaveText("boss");
  await expect(row(page, "reaction").locator(".cluster-label")).toHaveText("reaction wave");
  await page.waitForTimeout(2_000);
  await expect(row(page, "topic")).toHaveCount(0);
  await expect(status(page)).toHaveCount(0);
  expect(modelRequests).toEqual([]);
});

test.describe("when the model cannot load", () => {
  test.use({ topicModel: "broken" });

  test("the board says so plainly and groups by shared words", async ({ page }) => {
    let sock: Sock | null = null;
    await mockTwitch(page, (s) => (sock = s));
    await page.goto("/");
    await enter(page, "nomodel");
    await expect.poll(() => sock !== null).toBe(true);
    say(sock!, ["LMAO", "KEKW", "LMAO", "the boss fight is so hard", "boss is unbeatable", "that boss though"]);
    await expect(status(page)).toHaveText("Topics unavailable — grouped by shared words", { timeout: 15_000 });
    await expect(row(page, "shared word").locator(".cluster-label")).toHaveText("boss");
    await expect(row(page, "reaction").locator(".cluster-label")).toHaveText("reaction wave");
    await expect(page.locator(".how-grouping summary")).toHaveText("How grouping works");
    await page.locator(".how-grouping summary").click();
    await expect(page.locator(".how-grouping")).toContainText("Shared word"); // the word rules' own explanation
  });
});

test("switching channel never shows the previous channel's topics", async ({ page }) => {
  const socks = new Map<string, Sock>();
  await mockTwitch(page, (s) => socks.set(s.ch, s));
  await page.goto("/");
  await enter(page, "alpha");
  await expect.poll(() => socks.has("alpha")).toBe(true);
  say(socks.get("alpha")!, NO_AUDIO);
  await expect(row(page, "topic")).toHaveCount(1, { timeout: 20_000 });

  // alpha's chat keeps coming while the visitor switches: a burst the model is still reading
  say(socks.get("alpha")!, MUTED.concat(NO_AUDIO.map((t) => `${t} again`)));
  await page.getByRole("button", { name: "Switch channel" }).click();
  await page.getByPlaceholder("channel…").fill("bravo");
  await page.getByPlaceholder("channel…").press("Enter");
  await expect(page.locator(".ws-channel-name")).toHaveText("#bravo");
  await expect.poll(() => socks.has("bravo")).toBe(true);
  say(socks.get("bravo")!, WHAT_GAME);

  await expect(row(page, "question")).toHaveCount(1, { timeout: 20_000 });
  await page.waitForTimeout(3_000); // two recounts: time for a stale answer to leak
  const labels = await page.locator(".cluster-label").allTextContents();
  expect(labels.some((l) => /audio|sound|hear|mic/.test(l))).toBe(false);
  await expect(row(page, "topic")).toHaveCount(0);
  await expect(status(page)).toHaveCount(0); // the model still works after the switch
});

test("400 msg/s: the model falls behind honestly, the page stays responsive, then it catches up", async ({ page }) => {
  test.setTimeout(60_000);
  // 300 different texts (12 subjects x 25 remarks), sent round-robin by different chatters
  const subjects = ["the boss", "this map", "the build", "his aim", "the music", "the ending", "that team", "the chat", "this run", "the camera", "the stream", "the update"];
  const remarks = ["is great", "is awful", "looks broken", "is so good", "needs a fix", "is hilarious", "is perfect", "feels slow", "is too hard", "is underrated",
    "is overrated", "was a mistake", "is clean", "is messy", "keeps lagging", "is insane", "is cursed", "is beautiful", "is boring", "is a classic",
    "makes no sense", "is getting better", "is getting worse", "is peak", "is mid"];
  const vocabulary = subjects.flatMap((s) => remarks.map((r) => `${s} ${r}`));

  await page.addInitScript(() => {
    const w = window as unknown as { __maxGap: number; __statuses: string[] };
    w.__maxGap = 0;
    w.__statuses = [];
    let last = performance.now();
    const frame = (t: number) => {
      w.__maxGap = Math.max(w.__maxGap, t - last);
      last = t;
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
    new MutationObserver(() => {
      const s = document.querySelector(".topic-status")?.textContent ?? "";
      if (s && w.__statuses.at(-1) !== s) w.__statuses.push(s);
    }).observe(document, { childList: true, subtree: true, characterData: true });
  });
  let sock: Sock | null = null;
  await mockTwitch(page, (s) => (sock = s));
  await page.goto("/");
  await enter(page, "burst");
  await expect.poll(() => sock !== null).toBe(true);
  say(sock!, ["hello", "hi"]);
  await expect(page.locator(".msg")).toHaveCount(2);
  await expect(status(page)).toHaveCount(0, { timeout: 20_000 }); // the model is loaded and idle

  await page.evaluate(() => ((window as unknown as { __maxGap: number }).__maxGap = 0));
  const t0 = Date.now();
  let n = 0;
  await new Promise<void>((done) => {
    const timer = setInterval(() => {
      if (Date.now() - t0 > 5_000) return clearInterval(timer), done();
      const batch: string[] = [];
      for (let k = 0; k < 20; k++) batch.push(line(sock!.ch, vocabulary[n++ % vocabulary.length]));
      sock!.ws.send(batch.join("\r\n"));
    }, 50);
  });
  const burstEnd = Date.now();
  await expect(status(page)).toHaveCount(0, { timeout: 30_000 });
  const caughtUpMs = Date.now() - burstEnd;
  const { maxGap, statuses } = await page.evaluate(() => {
    const w = window as unknown as { __maxGap: number; __statuses: string[] };
    return { maxGap: w.__maxGap, statuses: w.__statuses };
  });
  const topics = await page.locator(".cluster-chip").allTextContents();
  console.log(
    `[topics burst] ${n} messages in ${(burstEnd - t0) / 1000}s (${vocabulary.length} distinct) · ` +
      `longest frame gap ${Math.round(maxGap)}ms · caught up ${caughtUpMs}ms after the burst · ` +
      `statuses seen: ${JSON.stringify(statuses.slice(0, 6))} · chips: ${JSON.stringify(topics)}`,
  );
  expect(statuses.some((s) => /new messages? not read yet$/.test(s))).toBe(true); // said, not hidden
  expect(maxGap).toBeLessThan(300); // no visible freeze while the model works
  expect(topics.some((c) => c === "topic" || c === "question")).toBe(true);
});
