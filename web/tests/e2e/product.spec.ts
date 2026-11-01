import { test, expect, type Page, type WebSocketRoute } from "./fixtures";

// The audience timeline, the questions panel, the OBS overlay and its setup dialog, in the real
// page. Chat comes from a Playwright-mocked Twitch socket: a TEST FIXTURE ONLY, which drives the
// same client code a real Twitch socket does. Nothing here ships in the app.

let seq = 0;
function line(channel: string, text: string, who = `Viewer${++seq}`): string {
  const ts = Date.now();
  return (
    `@display-name=${who};id=p-${++seq}-${ts};room-id=1;tmi-sent-ts=${ts};user-type= ` +
    `:${who.toLowerCase()}!u@u.tmi.twitch.tv PRIVMSG #${channel} :${text}`
  );
}

type Sock = { ws: WebSocketRoute; ch: string };
/**
 * A mocked Twitch. `ack: false` is a channel that does not exist: Twitch never confirms the JOIN.
 * `opened` counts the connections the page made (a mocked socket raises no "websocket" event).
 */
async function mockTwitch(page: Page, onJoin: (s: Sock) => void = () => {}, { ack = true } = {}) {
  const seen = { opened: 0 };
  await page.routeWebSocket(/irc-ws\.chat\.twitch\.tv/, (ws) => {
    seen.opened++;
    ws.onMessage((msg) => {
      const s = typeof msg === "string" ? msg : msg.toString();
      if (s.startsWith("PING")) ws.send(":tmi.twitch.tv PONG tmi.twitch.tv :twinky");
      const m = /^JOIN #(\w+)/.exec(s);
      if (m && ack) {
        ws.send(`@room-id=1 :tmi.twitch.tv ROOMSTATE #${m[1]}`);
        onJoin({ ws, ch: m[1] });
      }
    });
  });
  return seen;
}
const say = (s: Sock, texts: string[], who?: string) => texts.forEach((t) => s.ws.send(line(s.ch, t, who)));

/** Chat spread over time, as a real chat is: `texts` round-robin, one every `everyMs`, for `forMs`. */
function stream(s: Sock, texts: string[], everyMs: number, forMs: number): Promise<void> {
  return new Promise((done) => {
    let i = 0;
    const t0 = Date.now();
    const timer = setInterval(() => {
      if (Date.now() - t0 > forMs) return clearInterval(timer), done();
      s.ws.send(line(s.ch, texts[i++ % texts.length]));
    }, everyMs);
  });
}

async function enter(page: Page, channel: string) {
  await page.getByPlaceholder("enter a twitch channel").fill(channel);
  await page.getByRole("button", { name: "Watch live" }).click();
  await expect(page.locator(".ws-channel-name")).toHaveText(`#${channel}`);
}
async function connect(page: Page, channel: string, url = "/"): Promise<Sock> {
  let sock: Sock | null = null;
  await mockTwitch(page, (s) => (sock = s));
  await page.goto(url);
  await enter(page, channel);
  await expect.poll(() => sock !== null).toBe(true);
  return sock!;
}

const CHAT = ["LUL", "KEKW", "LMAO", "clip it", "clip it", "W", "W", "first"];

// ---------------------------------------------------------------------------------------------
// Audience timeline
// ---------------------------------------------------------------------------------------------

test.describe("audience timeline", () => {
  test("empty until chat arrives, then real slices; before listening began is marked unknown, not zero", async ({ page }) => {
    const sock = await connect(page, "timeline", "/?topics=off");
    await page.getByRole("radio", { name: "30s" }).click();
    await expect(page.locator(".tl-empty")).toHaveText("Nothing to chart yet — the timeline fills in as messages arrive.");

    await stream(sock, CHAT, 120, 7_000);
    await expect(page.locator(".tl-title")).toHaveText("Audience timeline");
    await expect(page.locator(".tl-head .muted-tiny")).toHaveText("per 3s");
    // the session is younger than the window: the part before it is drawn as unknown, in both panels
    await expect(page.locator(".tl-unknown")).toHaveCount(2);
    await expect(page.locator(".tl-unknown-k")).toBeVisible();
    // one line per leading group, each named in the legend, in the board's own words
    const legend = await page.locator(".tl-leg-label").allTextContents();
    expect(legend.length).toBeGreaterThanOrEqual(2);
    const board = await page.locator(".cluster-label").allTextContents();
    for (const l of legend) expect(board).toContain(l);
    // never a chart of zeros from before we connected: at most 30 s / 3 s slices, all since connecting
    const slices = await page.locator(".tl-pt-total, .tl-dot-total").count();
    expect(slices).toBeLessThanOrEqual(1);

    await page.getByRole("radio", { name: "5m" }).click();
    await expect(page.locator(".tl-head .muted-tiny")).toHaveText("per 20s");
    await page.getByRole("radio", { name: "1m" }).click();
    await expect(page.locator(".tl-head .muted-tiny")).toHaveText("per 5s");
  });

  test("hover reads a slice; a legend entry or a line opens the group on the board and lights its chat", async ({ page }) => {
    const sock = await connect(page, "timeline", "/?topics=off");
    await page.getByRole("radio", { name: "30s" }).click();
    await stream(sock, CHAT, 120, 8_000);
    const chart = page.locator(".tl-chart");
    await expect(page.locator(".tl-legend")).toBeVisible();

    const box = (await chart.boundingBox())!;
    await page.mouse.move(box.x + box.width - 30, box.y + box.height / 2);
    await expect(page.locator(".tl-tip")).toBeVisible();
    await expect(page.locator(".tl-tip-when")).toHaveText(/ago|now|filling/);
    await expect(page.locator(".tl-tip-row").first()).toContainText("all chat");
    await page.mouse.move(box.x - 40, box.y - 40);
    await expect(page.locator(".tl-tip")).toHaveCount(0);

    const first = page.locator(".tl-leg").first();
    const label = await first.locator(".tl-leg-label").textContent();
    await first.click();
    await expect(first).toHaveAttribute("aria-pressed", "true");
    await expect(page.locator(".cluster-sel .cluster-label")).toHaveText(label!);
    await expect(page.locator(".msg-lit").first()).toBeVisible();
    // the others step back, the chosen one stays at full strength
    await expect(page.locator(".tl-leg-dim")).not.toHaveCount(0);
    await first.click();
    await expect(page.locator(".cluster-sel")).toHaveCount(0);

    // the line itself is a target too (a wide invisible stroke over it): click a point on it — the
    // middle of a polyline's bounding box is often not on the line
    const on = await page
      .locator(".tl-hit")
      .first()
      .evaluate((p: SVGPathElement) => {
        const q = p.getPointAtLength(p.getTotalLength() / 2);
        const m = p.getScreenCTM()!;
        return { x: q.x * m.a + q.y * m.c + m.e, y: q.x * m.b + q.y * m.d + m.f };
      });
    await page.mouse.click(on.x, on.y);
    await expect(page.locator(".cluster-sel")).toHaveCount(1);
    await page.screenshot({ path: "screenshots/desktop-timeline.png" });
  });

  test("keyboard: arrows read slice by slice, Escape closes the readout and keeps the group open", async ({ page }) => {
    const sock = await connect(page, "timeline", "/?topics=off");
    await page.getByRole("radio", { name: "30s" }).click();
    await stream(sock, CHAT, 120, 8_000);
    await page.locator(".tl-leg").first().click();
    await expect(page.locator(".cluster-sel")).toHaveCount(1);

    const readout = page.locator(".tl-chart .sr-only");
    await page.locator(".tl-chart").focus();
    await expect(readout).toContainText(/messages? in all/);
    const last = await readout.textContent();
    await page.keyboard.press("ArrowLeft");
    await expect(readout).not.toHaveText(last!);
    await page.keyboard.press("End");
    await expect(readout).toHaveText(last!);
    await page.keyboard.press("Home");
    await expect(page.locator(".tl-cross")).toHaveCount(1);
    await page.keyboard.press("Escape");
    await expect(page.locator(".tl-cross")).toHaveCount(0);
    await expect(page.locator(".cluster-sel")).toHaveCount(1); // Escape was the readout's, not the group's
  });

  test("switching channel starts the timeline over", async ({ page }) => {
    const socks = new Map<string, Sock>();
    await mockTwitch(page, (s) => socks.set(s.ch, s));
    await page.goto("/?topics=off");
    await enter(page, "alpha");
    await expect.poll(() => socks.has("alpha")).toBe(true);
    await stream(socks.get("alpha")!, CHAT, 120, 6_000);
    await expect(page.locator(".tl-legend")).toBeVisible();

    await page.getByRole("button", { name: "Switch channel" }).click();
    await page.getByPlaceholder("channel…").fill("bravo");
    await page.getByPlaceholder("channel…").press("Enter");
    await expect(page.locator(".ws-channel-name")).toHaveText("#bravo");
    await expect(page.locator(".tl-empty")).toBeVisible();
    await expect(page.locator(".tl-legend")).toHaveCount(0);
  });

  test("replay runs at 3x and its times are the recording's own", async ({ page }) => {
    await page.goto("/");
    await page.getByRole("button", { name: /recorded example/i }).click();
    await expect(page.locator(".src-replay")).toBeVisible();
    await expect(page.getByText("Times and rates are the recording's own.")).toBeVisible();
    await expect(page.locator(".pulse-sub")).toContainText("since you connected", { timeout: 15_000 });
    const t0 = Date.now();
    await page.waitForTimeout(5_000);
    const wall = (Date.now() - t0) / 1000;
    const sub = (await page.locator(".pulse-sub").textContent())!;
    const m = /the (\d+) seconds?|the (\d+) minutes?/.exec(sub);
    expect(m).not.toBeNull();
    const recorded = m![1] ? Number(m![1]) : Number(m![2]) * 60;
    // at 3x, 5 s on the clock is ~15 s of the recording; a wall-clock time base would say ~5
    expect(recorded).toBeGreaterThanOrEqual(2 * wall);
    await expect(page.locator(".tl-chart")).toBeVisible({ timeout: 15_000 });
    await page.screenshot({ path: "screenshots/desktop-replay.png" });
  });
});

// ---------------------------------------------------------------------------------------------
// Questions in chat
// ---------------------------------------------------------------------------------------------

test.describe("questions in chat", () => {
  test("the same question from several chatters is one row; one chatter repeating is not the room", async ({ page }) => {
    const sock = await connect(page, "questions", "/?topics=off");
    say(sock, ["what game is this"], "ann");
    say(sock, ["what game is this?"], "bob");
    say(sock, ["What game is this"], "cat");
    say(sock, ["what game is this", "what game is this"], "ann"); // the same chatter again
    say(
      sock,
      ["is the stream lagging?", "is the stream lagging?", "is the stream lagging?", "is the stream lagging?"],
      "spammer",
    );
    say(sock, ["what a play", "how crazy is that", "?", "LUL"], "dan"); // not questions

    const qs = page.locator(".qs");
    await expect(qs.locator(".qs-title")).toHaveText("Questions in chat");
    await expect(qs.locator(".qs-head .muted-tiny")).toHaveText("same wording");
    const row = qs.locator(".q");
    await expect(row).toHaveCount(1);
    await expect(row.locator(".q-text")).toHaveText(/what game is this/i);
    await expect(row.locator(".q-meta")).toHaveText("Asked by 3 chatters · 5 messages");

    // one chatter asking four times is listed once, as one chatter's question
    await expect(qs.locator(".qs-others summary")).toHaveText("1 other question, each from one chatter");
    await qs.locator(".qs-others summary").click();
    await expect(qs.locator(".qs-others .ev")).toHaveCount(1);
    await expect(qs.locator(".qs-others .q-times")).toHaveText(" ×4");

    // the evidence is the messages themselves
    await row.locator(".q-head").click();
    await expect(row.locator(".q-head")).toHaveAttribute("aria-expanded", "true");
    await expect(row.locator(".ev")).toHaveCount(5);
    await expect(row.locator(".q-how")).toHaveText("The same wording");
    const show = row.getByRole("button", { name: "Show on the board" });
    if (await show.count()) {
      await show.click();
      await expect(page.locator(".cluster-sel")).toHaveCount(1);
      await expect(row.getByRole("button", { name: "Shown on the board" })).toHaveAttribute("aria-pressed", "true");
    }
    // nothing claims to know whether a question was answered
    await expect(page.getByText(/unanswered|answered/i)).toHaveCount(0);
    await page.screenshot({ path: "screenshots/desktop-questions.png" });
  });

  test("nothing asked twice: says so, without inventing a question", async ({ page }) => {
    const sock = await connect(page, "questions", "/?topics=off");
    say(sock, ["LUL", "KEKW", "clip it", "clip it"]);
    say(sock, ["where is the timer?"], "ann");
    await expect(page.locator(".qs-empty")).toHaveText("No question asked by more than one chatter in the last 60 seconds.");
    await expect(page.locator(".qs .q")).toHaveCount(0);
  });

  test("by meaning: different wordings of one question are one row, with each wording as evidence", async ({ page }) => {
    const sock = await connect(page, "meaning");
    const asked = ["what game is this", "whats this game called", "game name?", "what is this game"];
    asked.forEach((t, i) => say(sock, [t], `asker${i}`));
    const row = page.locator(".qs .q");
    await expect(row).toHaveCount(1, { timeout: 20_000 });
    await expect(page.locator(".qs-head .muted-tiny")).toHaveText("by meaning");
    await expect(row.locator(".q-meta")).toHaveText("Asked by 4 chatters");
    await row.locator(".q-head").click();
    await expect(row.locator(".q-how")).toHaveText("Different wordings, grouped by meaning");
    const ev = await row.locator(".ev-text").allTextContents();
    expect(ev.sort()).toEqual([...asked].sort());
    await row.getByRole("button", { name: "Show on the board" }).click();
    await expect(page.locator(".cluster-sel .cluster-chip")).toHaveText("question");
  });

  test.describe("when the model cannot load", () => {
    test.use({ topicModel: "broken" });
    test("questions fall back to the same wording, and say so", async ({ page }) => {
      const sock = await connect(page, "fallback");
      ["what game is this", "whats this game called", "game name?", "what is this game"].forEach((t, i) =>
        say(sock, [t], `asker${i}`),
      );
      await expect(page.locator(".topic-status")).toHaveText("Topics unavailable — grouped by shared words", { timeout: 15_000 });
      await expect(page.locator(".qs-head .muted-tiny")).toHaveText("same wording");
      // four different wordings, four chatters: no wording repeated, so no row claims they are one
      await expect(page.locator(".qs .q")).toHaveCount(0);
      await expect(page.locator(".qs-others summary")).toHaveText("4 other questions, each from one chatter");
      await page.screenshot({ path: "screenshots/desktop-fallback.png" });
    });
  });
});

// ---------------------------------------------------------------------------------------------
// OBS overlay
// ---------------------------------------------------------------------------------------------

const OVERLAY_CHAT = [
  ...Array.from({ length: 6 }, () => "LUL"),
  ...Array.from({ length: 5 }, () => "clip it"),
  ...Array.from({ length: 4 }, () => "W"),
  ...Array.from({ length: 3 }, () => "first"),
  ...Array.from({ length: 2 }, () => "o7"),
];

async function overlay(page: Page, channel: string, query = ""): Promise<Sock> {
  let sock: Sock | null = null;
  await mockTwitch(page, (s) => (sock = s));
  await page.goto(`/?channel=${channel}&overlay=1${query}`);
  await expect.poll(() => sock !== null).toBe(true);
  return sock!;
}

/** Alpha of a screenshot's pixel at CSS point (x, y), 0-255, whatever the device pixel ratio. */
async function alphaAt(png: Buffer, page: Page, x: number, y: number): Promise<number> {
  // decoded by the browser itself, on a detached canvas: nothing is drawn on the page
  return page.evaluate(
    async ([b64, x, y]) => {
      const img = new Image();
      img.src = `data:image/png;base64,${b64}`;
      await img.decode();
      const k = img.naturalWidth / innerWidth;
      const c = document.createElement("canvas");
      c.width = img.naturalWidth;
      c.height = img.naturalHeight;
      const g = c.getContext("2d")!;
      g.drawImage(img, 0, 0);
      const px = Math.min(c.width - 1, Math.round(Number(x) * k)), py = Math.min(c.height - 1, Math.round(Number(y) * k));
      return g.getImageData(px, py, 1, 1).data[3];
    },
    [png.toString("base64"), x, y] as const,
  );
}

test.describe("OBS overlay", () => {
  test("its own page: no landing, no controls, a transparent page, the top three groups from its own connection", async ({
    page,
  }) => {
    await page.setViewportSize({ width: 420, height: 240 });
    const sock = await overlay(page, "overlaych", "&topics=off");
    OVERLAY_CHAT.forEach((t) => say(sock, [t]));

    await expect(page.locator(".ov-row")).toHaveCount(3);
    await expect(page.locator(".ov-chan")).toHaveText("#overlaych chat");
    await expect(page.locator(".ov-win")).toHaveText("reactions & repeats · last 1m");
    await expect(page.locator(".hero-title")).toHaveCount(0);
    await expect(page.locator("button, input, select, a")).toHaveCount(0); // nothing to click on stream
    await expect(page).toHaveTitle("#overlaych · Twinky overlay");
    const labels = await page.locator(".ov-label").allTextContents();
    expect(labels[0]).toBe("Chat is laughing");
    expect(labels).toContain("clip it");

    // the page paints nothing: OBS composites it over the video
    const bg = await page.evaluate(() => [
      getComputedStyle(document.documentElement).backgroundColor,
      getComputedStyle(document.body).backgroundColor,
    ]);
    expect(bg).toEqual(["rgba(0, 0, 0, 0)", "rgba(0, 0, 0, 0)"]);
    await page.waitForTimeout(500);
    const png = await page.screenshot({
      omitBackground: true,
      path: "screenshots/overlay-420x240.png",
    });
    const card = (await page.locator(".ov-card").boundingBox())!;
    expect(await alphaAt(png, page, 0, 0)).toBeLessThanOrEqual(8); // outside the card: see-through
    expect(await alphaAt(png, page, 419, 239)).toBeLessThanOrEqual(8);
    expect(await alphaAt(png, page, card.x + card.width / 2, card.y + card.height / 2)).toBeGreaterThan(150);
  });

  test("with the model: groups by meaning, and says so while it loads", async ({ page }) => {
    await page.setViewportSize({ width: 420, height: 240 });
    const sock = await overlay(page, "overlaytopics");
    say(sock, ["no audio", "audio is gone", "cant hear anything", "no sound", "LUL", "KEKW", "LUL"]);
    await expect(page.locator(".ov-row")).not.toHaveCount(0);
    await expect(page.locator(".ov-meta", { hasText: "topic" })).toHaveCount(1, { timeout: 20_000 });
    await expect(page.locator(".ov-win")).toHaveText("last 1m");
    await page.screenshot({
      omitBackground: true,
      path: "screenshots/overlay-topics.png",
    });
  });

  test("no channel, or not a channel name: says how to fix the link, opens no connection", async ({ page }) => {
    const twitch = await mockTwitch(page);
    await page.goto("/?overlay=1");
    await expect(page.locator(".ov-help")).toContainText("no channel in the address");
    await expect(page.locator(".ov-help code")).toHaveText("?channel=yourname&overlay=1");
    await page.goto("/?channel=not%20a%20channel!&overlay=1");
    await expect(page.locator(".ov-help")).toContainText("“not a channel!” is not a Twitch channel name.");
    await page.waitForTimeout(500);
    expect(twitch.opened).toBe(0);
    await expect(page.locator(".hero-title")).toHaveCount(0);
  });

  test("a channel that does not exist says so", async ({ page }) => {
    await mockTwitch(page, () => {}, { ack: false });
    await page.goto("/?channel=zzqqnotreal&overlay=1");
    await expect(page.locator(".ov-status")).toHaveText("Connecting to #zzqqnotreal chat…");
    await expect(page.locator(".ov-status")).toHaveText("No Twitch channel called #zzqqnotreal", { timeout: 15_000 });
    await expect(page.locator(".ov-status .listening")).toHaveCount(0); // terminal: nothing spins
  });

  test("a silent chat is called quiet; a lost connection is called reconnecting, then recovers", async ({ page, context }) => {
    test.setTimeout(45_000);
    const sock = await overlay(page, "quietch", "&topics=off");
    await expect(page.locator(".ov-status")).toHaveText("Listening to #quietch chat");
    await expect(page.locator(".ov-status")).toHaveText("#quietch chat is quiet", { timeout: 20_000 });
    OVERLAY_CHAT.forEach((t) => say(sock, [t]));
    await expect(page.locator(".ov-row")).toHaveCount(3);
    await expect(page.locator(".ov-status")).toHaveCount(0);

    await context.setOffline(true);
    await expect(page.locator(".ov-status")).toHaveText("Reconnecting to chat…", { timeout: 10_000 });
    await expect(page.locator(".ov-row")).toHaveCount(3); // what was counted stays up, with the status under it
    await context.setOffline(false);
    await expect(page.locator(".ov-status")).toHaveCount(0, {
      timeout: 15_000,
    });
  });

  for (const [w, h] of [
    [320, 180],
    [420, 240],
    [640, 360],
    [1280, 720],
    [1920, 1080],
    [400, 150],
  ] as const) {
    test(`fits a ${w}x${h} browser source`, async ({ page }) => {
      await page.setViewportSize({ width: w, height: h });
      const sock = await overlay(page, "sizes", "&topics=off");
      OVERLAY_CHAT.forEach((t) => say(sock, [t]));
      await expect(page.locator(".ov-row")).toHaveCount(3);
      const fit = await page.evaluate(() => ({
        x: document.documentElement.scrollWidth - innerWidth,
        y: document.documentElement.scrollHeight - innerHeight,
        font: parseFloat(getComputedStyle(document.querySelector(".ov-label")!).fontSize),
      }));
      expect(fit.x).toBeLessThanOrEqual(0);
      expect(fit.y).toBeLessThanOrEqual(0);
      expect(fit.font).toBeGreaterThanOrEqual(12);
      // every row shown is wholly on screen; a very short source keeps the two leading rows
      const visible = page.locator(".ov-row:visible");
      const n = await visible.count();
      expect(n).toBe(h <= 170 ? 2 : 3);
      for (let i = 0; i < n; i++) await expect(visible.nth(i)).toBeInViewport({ ratio: 1 });
      if (w === 1920 || w === 400)
        await page.screenshot({
          omitBackground: true,
          path: `screenshots/overlay-${w}x${h}.png`,
        });
    });
  }

  // anything still moving: running, and longer than the 0.001 ms reduced motion leaves behind
  const moving = (page: Page) =>
    page.evaluate(
      () =>
        document.getAnimations().filter((x) => x.playState === "running" && Number(x.effect?.getComputedTiming().duration) > 1)
          .length,
    );
  // every slide a row starts (the rows slide with the Web Animations API, src/ui/Overlay.tsx)
  const slides = (page: Page) => page.evaluate(() => (window as unknown as { __slides: number }).__slides);
  async function overtake(page: Page, channel: string) {
    await page.addInitScript(() => {
      const w = window as unknown as { __slides: number };
      w.__slides = 0;
      const animate = Element.prototype.animate;
      Element.prototype.animate = function (this: Element, ...args: Parameters<Element["animate"]>) {
        if (this.classList.contains("ov-row")) w.__slides++;
        return animate.apply(this, args);
      };
    });
    await page.setViewportSize({ width: 420, height: 240 });
    const sock = await overlay(page, channel, "&topics=off");
    say(sock, ["clip it", "clip it", "clip it", "send it", "send it"]);
    await expect(page.locator(".ov-row")).toHaveCount(2);
    await page.waitForTimeout(800); // the rows' entrance is over
    say(sock, ["send it", "send it", "send it", "send it"]);
    await expect(page.locator(".ov-label").first()).toHaveText("send it");
  }
  test("rows slide to their new place when the ranking changes", async ({ page }) => {
    await overtake(page, "moving");
    expect(await slides(page)).toBeGreaterThan(0);
  });
  test.describe("reduced motion", () => {
    test("rows change places without sliding", async ({ page }) => {
      await page.emulateMedia({ reducedMotion: "reduce" });
      await overtake(page, "calm");
      expect(await slides(page)).toBe(0);
      expect(await moving(page)).toBe(0); // nor anything else, CSS included
      await page.screenshot({
        omitBackground: true,
        path: "screenshots/overlay-reduced-motion.png",
      });
    });
  });

  test("runs on its own: a separate browser with no dashboard open", async ({ page, browser }) => {
    const sock = await connect(page, "together", "/?topics=off");
    OVERLAY_CHAT.forEach((t) => say(sock, [t]));
    await expect(page.locator(".cluster")).not.toHaveCount(0);

    const obs = await browser.newContext({
      viewport: { width: 420, height: 240 },
    });
    const ov = await obs.newPage();
    const ovSock = await overlay(ov, "together", "&topics=off");
    await page.close(); // the dashboard is gone; the overlay has its own connection
    OVERLAY_CHAT.forEach((t) => say(ovSock, [t]));
    await expect(ov.locator(".ov-row")).toHaveCount(3);
    await obs.close();
  });
});

// ---------------------------------------------------------------------------------------------
// Setting the overlay up
// ---------------------------------------------------------------------------------------------

test("OBS setup: the link, copy, recommended size and a preview — and nothing private in the link", async ({
  page,
  context,
  browserName,
}) => {
  if (browserName === "chromium") await context.grantPermissions(["clipboard-read", "clipboard-write"]);
  const sock = await connect(page, "setupch");
  OVERLAY_CHAT.forEach((t) => say(sock, [t]));
  await expect(page.locator(".cluster")).not.toHaveCount(0);

  await page.getByRole("radio", { name: "5m" }).click();
  await page.getByRole("button", { name: "OBS overlay" }).click();
  const dialog = page.getByRole("dialog", {
    name: "Show #setupch chat on stream",
  });
  await expect(dialog).toBeVisible();
  const field = dialog.getByLabel("Overlay link");
  const origin = new URL(page.url()).origin;
  await expect(field).toHaveValue(`${origin}/?channel=setupch&overlay=1&window=5m`);

  await dialog.getByRole("button", { name: "Copy" }).click();
  await expect(dialog.getByRole("button", { name: "Copied" })).toBeVisible();
  if (browserName === "chromium")
    expect(await page.evaluate(() => navigator.clipboard.readText())).toBe(await field.inputValue());

  await dialog.getByLabel(/Lighter/).check();
  await expect(field).toHaveValue(`${origin}/?channel=setupch&overlay=1&window=5m&topics=off`);
  const params = [...new URL(await field.inputValue()).searchParams.keys()];
  expect(params.every((k) => ["channel", "overlay", "window", "topics"].includes(k))).toBe(true);
  expect(await field.inputValue()).not.toMatch(/token|key|oauth|secret|auth/i);

  await expect(dialog.locator(".ovs-steps")).toContainText("width 420 and height 240");
  await expect(dialog.locator(".ovs-stage .ov-row")).not.toHaveCount(0);
  await expect(dialog.getByRole("link", { name: "Open the overlay on its own" })).toHaveAttribute(
    "href",
    await field.inputValue(),
  );
  await page.screenshot({ path: "screenshots/desktop-overlay-setup.png" });

  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(page.locator(".ws-channel-name")).toHaveText("#setupch"); // Escape closed the dialog, not the channel
});

test("the setup preview reuses the page's own grouping: opening it starts no second model or connection", async ({ page }) => {
  const workers: string[] = [];
  page.on("worker", (w) => workers.push(w.url()));
  let sock: Sock | null = null;
  const twitch = await mockTwitch(page, (s) => (sock = s));
  await page.goto("/");
  await enter(page, "onemodel");
  await expect.poll(() => sock !== null).toBe(true);
  say(sock!, ["no audio", "audio is gone", "cant hear anything", "no sound"]);
  await expect(page.locator(".cluster-chip", { hasText: /^topic$/ })).toHaveCount(1, { timeout: 20_000 });
  // the model's worker (in Chromium, also the WebAssembly runtime's threads) and one chat socket
  const before = { workers: workers.length, sockets: twitch.opened };
  expect(before.workers).toBeGreaterThanOrEqual(1);
  expect(before.sockets).toBe(1);

  await page.getByRole("button", { name: "OBS overlay" }).click();
  await expect(page.locator(".ovs-stage .ov-row")).not.toHaveCount(0);
  await page.waitForTimeout(1_500);
  expect({ workers: workers.length, sockets: twitch.opened }).toEqual(before);
});

test("overlay startup, and memory held to the session's cap under sustained chat (measured)", async ({ page, browserName }) => {
  await page.setViewportSize({ width: 420, height: 240 });
  let sock: Sock | null = null;
  await mockTwitch(page, (s) => (sock = s));
  const t0 = Date.now();
  await page.goto("/?channel=steady&overlay=1&topics=off");
  await expect(page.locator(".ov-card")).toBeVisible();
  const cardMs = Date.now() - t0;
  await expect.poll(() => sock !== null).toBe(true);
  const joinedMs = Date.now() - t0;
  say(sock!, OVERLAY_CHAT);
  await expect(page.locator(".ov-row")).toHaveCount(3);
  const rowsMs = Date.now() - t0;
  const js = await page.evaluate(() =>
    performance
      .getEntriesByType("resource")
      .filter((r) => r.name.endsWith(".js"))
      .reduce((n, r) => n + (r as PerformanceResourceTiming).encodedBodySize, 0),
  );

  // How much an overlay left running for hours can hold. Everything kept per message has a cap:
  // the session's 330 s of chat, at most 20,000 messages (src/engine/session.ts); the grouper's
  // per-message cache, pruned past twice the window + 1,000 (src/semantic/live.ts); 5,000 ids for
  // reconnect dedupe (src/twitch/irc.ts). Only chatter names grow without a cap, with distinct
  // chatters. 400 messages a second from 400 chatters, for 70 s by default; OVERLAY_SOAK_ROUNDS=30
  // runs 150 s, long enough to pass every cap. Heap measured after a forced GC, from the DevTools
  // protocol (Chromium only; WebKit exposes no figure).
  const cdp = browserName === "chromium" ? await page.context().newCDPSession(page) : null;
  const heap = async () => {
    if (!cdp) return null;
    await cdp.send("HeapProfiler.collectGarbage");
    return (await cdp.send("Runtime.getHeapUsage")).usedSize;
  };
  const texts = Array.from({ length: 600 }, (_, i) => `steady message number ${i} about the run`);
  const samples: (number | null)[] = [await heap()];
  let n = 0;
  const rounds = Number(process.env.OVERLAY_SOAK_ROUNDS ?? 14);
  test.setTimeout(30_000 + rounds * 7_000);
  for (let s = 0; s < rounds; s++) {
    await new Promise<void>((done) => {
      const t = Date.now();
      const timer = setInterval(() => {
        if (Date.now() - t > 5_000) return clearInterval(timer), done();
        sock!.ws.send(Array.from({ length: 20 }, () => line(sock!.ch, texts[n % texts.length], `chatter${n++ % 400}`)).join("\r\n"));
      }, 50);
    });
    samples.push(await heap());
  }
  const mb = (b: number | null) => (b === null ? "n/a" : `${(b / 1048576).toFixed(1)} MB`);
  console.log(
    `[overlay ${browserName}] card ${cardMs}ms · socket joined ${joinedMs}ms · 3 rows ${rowsMs}ms after navigation · ` +
      `JS ${(js / 1024).toFixed(0)} kB transferred · ${n} messages in ${rounds * 5} s · JS heap (after GC, every 5 s) ${samples.map(mb).join(" → ")}`,
  );
  await expect(page.locator(".ov-row")).not.toHaveCount(0);
  const [first, ...rest] = samples;
  if (first !== null) expect(Math.max(...(rest as number[]))).toBeLessThan(first + 40 * 1048576);
});
