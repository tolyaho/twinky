import { test, expect, type Page, type WebSocketRoute } from "@playwright/test";

// Deterministic browser tests for the unglamorous paths: reconnects, rapid switching, bursts,
// network loss, keyboard use, reduced motion and deep links. Every Twitch socket here is a
// Playwright-mocked server (TEST FIXTURE ONLY) driving the exact client code a real one does.

let seq = 0;
function line(channel: string, text: string, opts: { id?: string; name?: string } = {}): string {
  const ts = Date.now();
  const n = ++seq;
  const name = opts.name ?? `Viewer${n}`;
  const id = opts.id ?? `e2e-${n}-${ts}`;
  return (
    `@display-name=${name};id=${id};room-id=1;tmi-sent-ts=${ts};user-type= ` +
    `:${name.toLowerCase()}!u@u.tmi.twitch.tv PRIVMSG #${channel} :${text}`
  );
}

const ack = (channel: string) => `@room-id=1 :tmi.twitch.tv ROOMSTATE #${channel}`;

type OnJoin = (ws: WebSocketRoute, channel: string, conn: number) => void;

/** Mock Twitch: answers PING, acknowledges JOIN, then hands the socket to the scenario. */
async function mockTwitch(page: Page, onJoin: OnJoin): Promise<{ connections: () => number }> {
  let conns = 0;
  await page.routeWebSocket(/irc-ws\.chat\.twitch\.tv/, (ws) => {
    const conn = conns++;
    ws.onMessage((msg) => {
      const s = typeof msg === "string" ? msg : msg.toString();
      if (s.startsWith("PING")) ws.send(":tmi.twitch.tv PONG tmi.twitch.tv :twinky");
      const m = /^JOIN #(\w+)/.exec(s);
      if (m) {
        ws.send(ack(m[1]));
        onJoin(ws, m[1], conn);
      }
    });
  });
  return { connections: () => conns };
}

async function enter(page: Page, channel: string) {
  await page.getByPlaceholder("enter a twitch channel").fill(channel);
  await page.getByRole("button", { name: "Watch live" }).click();
  await expect(page.locator(".ws-channel-name")).toHaveText(`#${channel}`);
}

async function switchTo(page: Page, channel: string) {
  await page.getByRole("button", { name: "Switch channel" }).click();
  await page.getByPlaceholder("channel…").fill(channel);
  await page.getByPlaceholder("channel…").press("Enter");
}

const feedTexts = (page: Page) => page.locator(".msg-text").allTextContents();

test("reconnect after a dropped socket: resumes, and replayed ids are not shown twice", async ({ page }) => {
  await mockTwitch(page, (ws, ch, conn) => {
    // first socket: r0..r9, then the server drops it. second socket: r5..r14 (r5..r9 replayed).
    const ids = conn === 0 ? [0, 1, 2, 3, 4, 5, 6, 7, 8, 9] : [5, 6, 7, 8, 9, 10, 11, 12, 13, 14];
    ids.forEach((i, k) =>
      setTimeout(() => ws.send(line(ch, `message r${i}`, { id: `r${i}`, name: `P${i}` })), 50 + k * 40),
    );
    if (conn === 0) setTimeout(() => ws.close(), 700);
  });
  await page.goto("/");
  await enter(page, "xqc");
  await expect(page.locator(".badge")).toContainText("Reconnecting", { timeout: 5_000 });
  await expect.poll(async () => (await feedTexts(page)).length, { timeout: 10_000 }).toBe(15);
  const texts = await feedTexts(page);
  expect(new Set(texts).size).toBe(texts.length);
  await expect(page.locator(".badge")).toContainText("Live chat");
});

test("rapid channel switching: only the last channel's chat and clusters survive", async ({ page }) => {
  await mockTwitch(page, (ws, ch) => {
    let i = 0;
    const timer = setInterval(() => ws.send(line(ch, `from ${ch} ${i++}`)), 60);
    ws.onClose(() => clearInterval(timer));
  });
  await page.goto("/");
  await enter(page, "alpha");
  await expect(page.locator(".msg").first()).toBeVisible();
  await switchTo(page, "bravo");
  await switchTo(page, "charlie");
  await expect(page.locator(".ws-channel-name")).toHaveText("#charlie");
  await expect.poll(async () => page.locator(".cluster").count(), { timeout: 10_000 }).toBeGreaterThan(0);
  await page.waitForTimeout(1_500); // let any stale socket try to leak
  const texts = await feedTexts(page);
  expect(texts.length).toBeGreaterThan(0);
  expect(texts.every((t) => t.startsWith("from charlie"))).toBe(true);
  const labels = await page.locator(".cluster-label").allTextContents();
  expect(labels.some((l) => /alpha|bravo/.test(l))).toBe(false);
  await expect(page).toHaveURL(/\?channel=charlie$/);
});

test("burst: ~400 msgs/s stays responsive with a bounded DOM (measured)", async ({ page }) => {
  const RATE_PER_TICK = 20; // every 50ms -> 400 messages/second
  const DURATION_MS = 8_000;
  const sentAt = new Map<string, number>();
  const words = ["LUL", "KEKW", "W", "insane", "what happened?", "no way", "clip it", "GG", "LMAO"];

  await page.addInitScript(() => {
    const w = window as unknown as { __maxGap: number; __seen: Record<string, number> };
    w.__maxGap = 0;
    w.__seen = {};
    // Responsiveness = the longest gap between two painted frames. A frozen main thread shows up
    // here directly, whatever caused it.
    let last = performance.now();
    const frame = (t: number) => {
      w.__maxGap = Math.max(w.__maxGap, t - last);
      last = t;
      requestAnimationFrame(frame);
    };
    requestAnimationFrame(frame);
    new MutationObserver((records) => {
      for (const r of records)
        r.addedNodes.forEach((n) => {
          const m = /PROBE-(\d+)/.exec((n as HTMLElement).textContent ?? "");
          if (m && !(m[1] in w.__seen)) w.__seen[m[1]] = Date.now();
        });
    }).observe(document, { childList: true, subtree: true });
  });

  await mockTwitch(page, (ws, ch) => {
    const t0 = Date.now();
    let n = 0;
    let probe = 0;
    const timer = setInterval(() => {
      if (Date.now() - t0 > DURATION_MS) return clearInterval(timer);
      const batch: string[] = [];
      for (let k = 0; k < RATE_PER_TICK; k++) batch.push(line(ch, `${words[n++ % words.length]} ${n % 7}`));
      if (n % 400 === 0) {
        const id = String(probe++);
        sentAt.set(id, Date.now());
        batch.push(line(ch, `PROBE-${id}`));
      }
      ws.send(batch.join("\r\n")); // Twitch packs several lines per frame, too
    }, 50);
    ws.onClose(() => clearInterval(timer));
  });

  await page.goto("/");
  await enter(page, "xqc");
  await page.evaluate(() => ((window as unknown as { __maxGap: number }).__maxGap = 0)); // page load is not the burst
  await page.waitForTimeout(DURATION_MS + 1_500);

  const { maxGap, seen } = await page.evaluate(() => {
    const w = window as unknown as { __maxGap: number; __seen: Record<string, number> };
    return { maxGap: w.__maxGap, seen: w.__seen };
  });
  const latencies = [...sentAt].filter(([id]) => id in seen).map(([id, t]) => seen[id] - t);
  latencies.sort((a, b) => a - b);
  const median = latencies[Math.floor(latencies.length / 2)];
  const domMsgs = await page.locator(".msg").count();
  console.log(
    `[burst] ~${(RATE_PER_TICK * 1000) / 50} msg/s for ${DURATION_MS / 1000}s · DOM .msg=${domMsgs} · ` +
      `longest frame gap ${Math.round(maxGap)}ms · ` +
      `probe latency median=${median}ms max=${latencies.at(-1)}ms (n=${latencies.length})`,
  );

  // Calibrate the instrument: a deliberate 150ms block must show up as a frame gap, or a small
  // number above would mean a broken probe rather than a responsive page.
  await page.evaluate(
    () =>
      new Promise<void>((done) =>
        setTimeout(() => {
          const t = performance.now();
          while (performance.now() - t < 150) {
            /* busy */
          }
          setTimeout(done, 100);
        }, 0),
      ),
  );
  const calibrated = await page.evaluate(() => (window as unknown as { __maxGap: number }).__maxGap);
  // (frame timestamps are vsync-aligned, so a 150ms block reads as ~133-150ms)
  console.log(`[burst] calibration: a deliberate 150ms block read as ${Math.round(calibrated)}ms`);
  expect(calibrated).toBeGreaterThanOrEqual(100);

  expect(domMsgs).toBeLessThanOrEqual(160); // bounded feed
  expect(latencies.length).toBeGreaterThan(3);
  expect(median).toBeLessThan(1_000); // chat on screen within a second of the socket
  expect(maxGap).toBeLessThan(300); // no visible freeze
  // and the UI still answers a click straight away
  await page.locator(".cluster").first().click();
  await expect(page.locator(".evidence")).toBeVisible({ timeout: 1_000 });
});

test("network loss: says so, then recovers when the network returns", async ({ page, context }) => {
  let streaming = true;
  await mockTwitch(page, (ws, ch) => {
    const timer = setInterval(() => streaming && ws.send(line(ch, "still here")), 150);
    ws.onClose(() => clearInterval(timer));
  });
  await page.goto("/");
  await enter(page, "xqc");
  await expect(page.locator(".badge")).toContainText("Live chat");

  streaming = false;
  await context.setOffline(true);
  await expect(page.locator(".badge")).toContainText("No network");

  await context.setOffline(false);
  streaming = true;
  await expect(page.locator(".badge")).toContainText("Live chat", { timeout: 10_000 });
});

test("keyboard only: enter a channel, open a group, close it with Escape", async ({ page }) => {
  await mockTwitch(page, (ws, ch) => {
    for (let i = 0; i < 12; i++) setTimeout(() => ws.send(line(ch, i % 2 ? "LMAO" : "KEKW")), 40 * i);
  });
  await page.goto("/");
  const input = page.getByPlaceholder("enter a twitch channel");
  for (let i = 0; i < 6 && !(await input.evaluate((el) => el === document.activeElement)); i++) {
    await page.keyboard.press("Tab");
  }
  await expect(input).toBeFocused();
  await page.keyboard.type("xqc");
  await page.keyboard.press("Enter");
  await expect(page.locator(".cluster").first()).toBeVisible({ timeout: 10_000 });

  const cluster = page.locator(".cluster").first();
  for (let i = 0; i < 30 && !(await cluster.evaluate((el) => el === document.activeElement)); i++) {
    await page.keyboard.press("Tab");
  }
  await expect(cluster).toBeFocused();
  // the focus ring must be visible on the dark canvas (lavender, not the near-black default)
  const outline = await cluster.evaluate((el) => {
    const cs = getComputedStyle(el);
    return { style: cs.outlineStyle, color: cs.outlineColor };
  });
  expect(outline.style).toBe("solid");
  expect(outline.color).toBe("rgb(200, 184, 224)");

  await page.keyboard.press("Enter");
  await expect(cluster).toHaveAttribute("aria-expanded", "true");
  await expect(page.locator(".evidence .ev").first()).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(cluster).toHaveAttribute("aria-expanded", "false");
  await expect(page.locator(".evidence")).toHaveCount(0);
});

test("reduced motion: nothing slides, rolls or pulses", async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  let sock: { ws: WebSocketRoute; ch: string } | null = null;
  await mockTwitch(page, (ws, ch) => {
    sock = { ws, ch };
    for (let i = 0; i < 8; i++) setTimeout(() => ws.send(line(ch, "LMAO")), 40 * i);
  });
  await page.goto("/");
  await enter(page, "xqc");
  await expect(page.locator(".cluster").first()).toBeVisible({ timeout: 10_000 });
  // CSS: every keyframe and transition is collapsed by the global rule
  const durations = await page.evaluate(() =>
    [".zone", ".cluster", ".num-in", ".dot-pulse", ".seg-thumb"].map((sel) => {
      const el = document.querySelector(sel);
      if (!el) return 0;
      const cs = getComputedStyle(el);
      return Math.max(parseFloat(cs.animationDuration) || 0, parseFloat(cs.transitionDuration) || 0);
    }),
  );
  for (const d of durations) expect(d).toBeLessThan(0.01);
  // script-driven motion (new messages, reordering, evidence) must not start at all: sample the
  // document's running animations while chat, counts and a group opening all change
  await page.evaluate(() => {
    (window as unknown as { __maxRunning: number }).__maxRunning = 0;
    const probe = () => {
      // CSS motion is collapsed to 0.001ms by the global rule (checked above); anything longer
      // that is running is motion the page started anyway
      const n = document
        .getAnimations()
        .filter((a) => a.playState === "running")
        .filter((a) => Number(a.effect?.getComputedTiming().activeDuration ?? 0) > 1).length;
      const w = window as unknown as { __maxRunning: number };
      w.__maxRunning = Math.max(w.__maxRunning, n);
      requestAnimationFrame(probe);
    };
    requestAnimationFrame(probe);
  });
  for (let i = 0; i < 6; i++) sock!.ws.send(line(sock!.ch, "dracula"));
  for (let i = 0; i < 6; i++) sock!.ws.send(line(sock!.ch, "LMAO"));
  await page.locator(".cluster").first().click();
  await expect(page.locator(".evidence")).toBeVisible();
  await page.waitForTimeout(2_000);
  expect(await page.evaluate(() => (window as unknown as { __maxRunning: number }).__maxRunning)).toBe(0);
});

test("deep link: ?channel= opens the channel, back returns to the start", async ({ page }) => {
  await mockTwitch(page, () => {});
  await page.goto("/");
  await page.goto("/?channel=XQC");
  await expect(page.locator(".ws-channel-name")).toHaveText("#xqc");
  await expect(page).toHaveURL(/\?channel=xqc$/); // normalised in place
  await expect(page).toHaveTitle("#xqc · Twinky");

  await page.locator(".ws-brand").click();
  await expect(page.locator(".hero-title")).toBeVisible();
  await page.goBack();
  await expect(page.locator(".ws-channel-name")).toHaveText("#xqc");
  await page.goBack(); // the history entry before the deep link: the landing page
  await expect(page.locator(".hero-title")).toBeVisible();

  await page.goto("/?channel=not%20a%20name!");
  await expect(page.locator(".hero-title")).toBeVisible(); // malformed -> landing, never a socket
});
