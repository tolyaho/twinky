import { test, expect, type Page, type WebSocketRoute } from "@playwright/test";

// The broadcast-status path and the motion/feedback layer. Twitch chat is a Playwright-mocked
// socket and `/api/twitch-status` a mocked route (TEST FIXTURES ONLY): the deployed endpoint has
// no Twitch app credentials, so these are the only way to exercise an authoritative "offline".

let seq = 0;
function line(channel: string, text: string, name?: string): string {
  const ts = Date.now();
  const n = ++seq;
  const who = name ?? `Viewer${n}`;
  return (
    `@display-name=${who};id=pol-${n}-${ts};room-id=1;tmi-sent-ts=${ts};user-type= ` +
    `:${who.toLowerCase()}!u@u.tmi.twitch.tv PRIVMSG #${channel} :${text}`
  );
}

type OnJoin = (ws: WebSocketRoute, channel: string) => void;

/** Mock Twitch chat. `ack: false` behaves like a channel that does not exist (no JOIN reply). */
async function mockTwitch(page: Page, onJoin: OnJoin = () => {}, ack = true) {
  await page.routeWebSocket(/irc-ws\.chat\.twitch\.tv/, (ws) => {
    ws.onMessage((msg) => {
      const s = typeof msg === "string" ? msg : msg.toString();
      if (s.startsWith("PING")) ws.send(":tmi.twitch.tv PONG tmi.twitch.tv :twinky");
      const m = /^JOIN #(\w+)/.exec(s);
      if (m && ack) {
        ws.send(`@room-id=1 :tmi.twitch.tv ROOMSTATE #${m[1]}`);
        onJoin(ws, m[1]);
      }
    });
  });
}

interface Reply {
  status?: number;
  body?: Record<string, unknown>;
  delayMs?: number;
}

/** Mock the status endpoint; `reply` sees the login and how many times it has been asked. */
async function mockStatus(page: Page, reply: (login: string, n: number) => Reply) {
  const calls: string[] = [];
  await page.route(/\/api\/twitch-status/, async (route) => {
    const login = new URL(route.request().url()).searchParams.get("login") ?? "";
    calls.push(login);
    const r = reply(login, calls.filter((c) => c === login).length);
    if (r.delayMs) await new Promise((res) => setTimeout(res, r.delayMs));
    await route
      .fulfill({
        status: r.status ?? 200,
        contentType: "application/json",
        body: JSON.stringify(r.body ?? {}),
      })
      .catch(() => {}); // the page may have navigated away meanwhile
  });
  return { calls };
}

const offline = (extra: Record<string, unknown> = {}) => ({
  body: { state: "offline", configured: true, checkedAt: Date.now(), recheckAfterMs: 60_000, ...extra },
});
const live = (extra: Record<string, unknown> = {}) => ({
  body: {
    state: "live",
    configured: true,
    checkedAt: Date.now(),
    startedAt: Date.now() - (2 * 60 + 14) * 60_000,
    recheckAfterMs: 60_000,
    ...extra,
  },
});

async function enter(page: Page, channel: string) {
  await page.getByPlaceholder("enter a twitch channel").fill(channel);
  await page.getByRole("button", { name: "Watch live" }).click();
  await expect(page.locator(".ws-channel-name")).toHaveText(`#${channel}`);
}

test("off air: Twitch says offline and chat is silent -> a calm off-air screen with real actions", async ({ page }) => {
  await mockTwitch(page);
  await mockStatus(page, () => offline());
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto("/");
  await enter(page, "sleepystreamer");

  await expect(page.locator(".board-empty-title")).toHaveText("#sleepystreamer is off air");
  await expect(page.locator(".bc-pill")).toHaveText("Off air");
  // a settled state: nothing in the board or the header pretends to be working on it
  await expect(page.locator(".board-empty .listening")).toHaveCount(0);
  await expect(page.locator(".ws-head .dot-pulse")).toHaveCount(0);
  await expect(page.locator(".feed-empty")).toContainText("Still listening");
  await expect(page.locator(".feed-empty .listening")).toHaveCount(0);
  await expect(page.locator(".msg")).toHaveCount(0);
  await page.waitForTimeout(400);
  await page.screenshot({ path: "screenshots/desktop-offair.png" });

  // the recorded demo is always labelled as a replay, before and after the click
  const demo = page.getByRole("button", { name: /Watch the recorded demo/ });
  await expect(demo.locator(".tag-replay")).toHaveText("Replay");
  await demo.click();
  await expect(page.locator(".src-replay")).toHaveText("REPLAY");
  await expect(page.locator(".replay-bar")).toContainText("not a live stream");
  await expect(page).toHaveURL(/\?replay$/);

  await page.goBack();
  await expect(page.locator(".board-empty-title")).toHaveText("#sleepystreamer is off air");
  await page.getByRole("button", { name: "Try another channel" }).click();
  await expect(page.getByPlaceholder("channel…")).toBeFocused();
  await page.keyboard.press("Escape");
  await page.getByRole("button", { name: "Back to start" }).click();
  await expect(page.locator(".hero-title")).toBeVisible();
});

test("off air but chat is active: real messages keep flowing under a quiet banner", async ({ page }) => {
  await mockTwitch(page, (ws, ch) => {
    const words = ["gg", "gg", "gg wp", "gg", "LUL", "LUL", "LUL", "LUL"];
    words.forEach((w, i) => setTimeout(() => ws.send(line(ch, w)), 100 + i * 60));
  });
  await mockStatus(page, () => offline());
  await page.goto("/");
  await enter(page, "afterparty");

  await expect(page.locator(".offair-bar")).toContainText("#afterparty is off air");
  await expect(page.locator(".offair-bar")).toContainText("still active");
  await expect(page.locator(".msg")).toHaveCount(8, { timeout: 5_000 });
  await expect(page.locator(".cluster").first()).toBeVisible({ timeout: 5_000 });
  await expect(page.locator(".board-empty")).toHaveCount(0);
  await expect(page.locator(".bc-pill")).toHaveText("Off air");
});

test("on air: the pill shows Twitch's own uptime; a silent chat says so instead of guessing", async ({ page }) => {
  test.setTimeout(45_000);
  await mockTwitch(page);
  await mockStatus(page, () => live());
  await page.goto("/");
  await enter(page, "focusmode");
  await expect(page.locator(".bc-pill")).toHaveText("On air · 2h 14m");
  await expect(page.locator(".bc-pill")).toHaveAttribute("title", /Twitch reports #focusmode is broadcasting/);
  // after the 12s quiet threshold, the board knows the stream is up and the chat is just slow
  await expect(page.locator(".board-empty-title")).toHaveText("On air, but chat is quiet", {
    timeout: 20_000,
  });
});

test("not found via Helix: answered at once, without waiting out the chat timeout", async ({ page }) => {
  await mockTwitch(page, () => {}, false); // chat never acknowledges the JOIN
  await mockStatus(page, () => ({ body: { state: "not_found", configured: true, checkedAt: Date.now() } }));
  await page.goto("/");
  const t0 = Date.now();
  await enter(page, "nosuchchannel42");
  await expect(page.locator(".board-empty-title")).toHaveText("No such channel", { timeout: 4_000 });
  expect(Date.now() - t0).toBeLessThan(4_000); // the credential-free fallback takes 8s
  await expect(page.locator(".badge")).toContainText("Not found");
  await expect(page.locator(".bc-pill")).toHaveCount(0);
});

test("status unknown: unconfigured or failing endpoint shows no pill and never blocks chat", async ({ page }) => {
  await mockTwitch(page, (ws, ch) => {
    for (let i = 0; i < 6; i++) setTimeout(() => ws.send(line(ch, "KEKW")), 100 + i * 50);
  });
  const status = await mockStatus(page, (login) =>
    login === "brokenstatus"
      ? { status: 500, body: { error: "boom" } }
      : { body: { state: "unknown", configured: false, reason: "unconfigured" } },
  );
  await page.goto("/");
  await enter(page, "nocreds");
  await expect(page.locator(".cluster").first()).toBeVisible({ timeout: 5_000 });
  await expect(page.locator(".bc-pill")).toHaveCount(0);
  await expect(page.locator(".offair-bar")).toHaveCount(0);
  await page.waitForTimeout(1_500);
  // unconfigured is a permanent answer: asked once, not polled
  expect(status.calls.filter((c) => c === "nocreds")).toHaveLength(1);

  await page.getByRole("button", { name: "Switch channel" }).click();
  await page.getByPlaceholder("channel…").fill("brokenstatus");
  await page.getByPlaceholder("channel…").press("Enter");
  await expect(page.locator(".ws-channel-name")).toHaveText("#brokenstatus");
  await expect(page.locator(".cluster").first()).toBeVisible({ timeout: 5_000 });
  await expect(page.locator(".bc-pill")).toHaveCount(0);
});

test("a slow status answer for the previous channel never lands on the new one", async ({ page }) => {
  await mockTwitch(page);
  await mockStatus(page, (login) => (login === "first" ? { ...offline(), delayMs: 1_500 } : live()));
  await page.goto("/");
  await enter(page, "first");
  // switch while the first channel's status request is still in flight
  await page.getByRole("button", { name: "Switch channel" }).click();
  await page.getByPlaceholder("channel…").fill("second");
  await page.getByPlaceholder("channel…").press("Enter");
  await expect(page.locator(".ws-channel-name")).toHaveText("#second");
  await expect(page.locator(".bc-pill")).toHaveText(/On air/);
  await page.waitForTimeout(2_000); // well past the stale reply
  await expect(page.locator(".bc-pill")).toHaveText(/On air/);
  await expect(page.locator(".offair-bar")).toHaveCount(0);
  await expect(page.locator(".board-empty-title")).not.toHaveText(/off air/);
});

test("rapid switching while status requests are in flight: only the last channel's answer shows", async ({ page }) => {
  await mockTwitch(page);
  const delays: Record<string, number> = { aaa: 1_200, bbb: 300, ccc: 900, ddd: 0 };
  await mockStatus(page, (login) =>
    login === "ddd" ? offline() : { ...live(), delayMs: delays[login] ?? 0 },
  );
  await page.goto("/");
  await enter(page, "aaa");
  for (const ch of ["bbb", "ccc", "ddd"]) {
    await page.getByRole("button", { name: "Switch channel" }).click();
    await page.getByPlaceholder("channel…").fill(ch);
    await page.getByPlaceholder("channel…").press("Enter");
  }
  await expect(page.locator(".ws-channel-name")).toHaveText("#ddd");
  await page.waitForTimeout(1_800);
  await expect(page.locator(".bc-pill")).toHaveText("Off air");
  await expect(page.locator(".board-empty-title")).toHaveText("#ddd is off air");
});

test("live -> offline: a recheck moves the board to off air without a reload", async ({ page }) => {
  await mockTwitch(page);
  await mockStatus(page, (_login, n) => (n === 1 ? live({ recheckAfterMs: 800 }) : offline()));
  await page.goto("/");
  await enter(page, "wrappingup");
  await expect(page.locator(".bc-pill")).toHaveText(/On air/);
  await expect(page.locator(".board-empty-title")).not.toHaveText(/off air/);
  await expect(page.locator(".bc-pill")).toHaveText("Off air", { timeout: 4_000 });
  await expect(page.locator(".board-empty-title")).toHaveText("#wrappingup is off air");
});

test("connection steps follow real socket events, then give way to the board", async ({ page }) => {
  let release: (() => void) | null = null;
  await page.routeWebSocket(/irc-ws\.chat\.twitch\.tv/, (ws) => {
    ws.onMessage((msg) => {
      const s = typeof msg === "string" ? msg : msg.toString();
      const m = /^JOIN #(\w+)/.exec(s);
      if (!m) return;
      // hold the JOIN acknowledgement until the test has looked at the "joining" step
      release = () => {
        ws.send(`@room-id=1 :tmi.twitch.tv ROOMSTATE #${m[1]}`);
        for (let i = 0; i < 6; i++) setTimeout(() => ws.send(line(m[1], "Pog")), 300 + i * 40);
      };
    });
  });
  await page.goto("/");
  await enter(page, "stepper");
  const steps = page.locator(".step");
  await expect(steps).toHaveCount(3);
  await expect(steps.nth(0)).toHaveClass(/step-done/);
  await expect(steps.nth(1)).toHaveClass(/step-active/);
  await expect(page.locator(".badge")).toContainText("Joining");
  await expect.poll(() => release !== null).toBe(true);
  release!();
  await expect(steps.nth(1)).toHaveClass(/step-done/);
  await expect(steps.nth(2)).toHaveClass(/step-active/);
  await expect(page.locator(".cluster").first()).toBeVisible({ timeout: 5_000 });
  await expect(page.locator(".steps")).toHaveCount(0);
});

test("replay button shows progress while the recording loads, and is labelled throughout", async ({ page }) => {
  await page.route(/\/assets\/replay-.*\.js$/, async (route) => {
    await new Promise((r) => setTimeout(r, 900));
    await route.continue();
  });
  await page.goto("/");
  const link = page.getByRole("button", { name: /recorded example|Loading the recording/ });
  await link.click();
  await expect(link).toHaveText("Loading the recording…");
  await expect(link).toHaveAttribute("aria-busy", "true");
  await expect(link).toBeDisabled();
  await expect(page.locator(".src-replay")).toHaveText("REPLAY", { timeout: 5_000 });
});

test("ranking holds still on near-ties and moves only on a clear overtake", async ({ page }) => {
  let sock: { ws: WebSocketRoute; ch: string } | null = null;
  await mockTwitch(page, (ws, ch) => (sock = { ws, ch }));
  await page.goto("/");
  await enter(page, "tiebreak");
  await expect.poll(() => sock !== null).toBe(true);
  const say = (text: string, n: number) => {
    for (let i = 0; i < n; i++) sock!.ws.send(line(sock!.ch, text));
  };
  const labels = () => page.locator(".cluster-label").allTextContents();

  say("LMAO", 6);
  say("dracula", 4);
  await expect.poll(async () => (await labels()).length, { timeout: 5_000 }).toBe(2);
  const [lead, chaser] = await labels();
  expect(lead).toBe("reaction wave"); // the six LMAOs

  // the chaser draws level, then edges one ahead: not a clear overtake, so nothing moves
  say("dracula", 3);
  await page.waitForTimeout(3_400); // two recounts
  expect(await labels()).toEqual([lead, chaser]);
  await expect(page.locator(".cluster-n").nth(1)).toHaveText("7");

  // a clear lead (2+) swaps them
  say("dracula", 2);
  await expect.poll(labels, { timeout: 5_000 }).toEqual([chaser, lead]);
});

test("opening a group unfolds its evidence on screen; Escape folds it and returns focus", async ({ page }) => {
  await page.setViewportSize({ width: 1024, height: 700 });
  await mockTwitch(page, (ws, ch) => {
    const words = [
      ...Array(8).fill("LMAO"),
      ...Array(5).fill("dracula"),
      ...["insane clutch", "insane", "so insane", "insane play"],
      ...Array(4).fill("W"),
    ];
    words.forEach((w, i) => setTimeout(() => ws.send(line(ch, w)), 80 + i * 30));
  });
  await page.goto("/");
  await enter(page, "evidence");
  const rows = page.locator(".cluster");
  await expect.poll(() => rows.count(), { timeout: 6_000 }).toBeGreaterThan(2);
  const last = rows.last();
  await last.click();
  const panel = page.locator(".evidence");
  await expect(panel).toBeVisible();
  // scrolled into view inside the list: the row itself, its first message and its Close button
  await expect(last).toBeInViewport({ timeout: 2_000 });
  await expect(panel.locator(".ev").first()).toBeInViewport();
  await expect(panel.getByRole("button", { name: "Close" })).toBeInViewport();
  await expect(last).toHaveAttribute("aria-expanded", "true");
  await page.keyboard.press("Escape");
  await expect(panel).toHaveCount(0);
  await expect(last).toHaveAttribute("aria-expanded", "false");

  // keyboard: focus is visible on the dark canvas, and Close puts it back on the row
  await last.focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Close" }).focus();
  await page.keyboard.press("Enter");
  await expect(page.locator(".evidence")).toHaveCount(0);
  await expect(last).toBeFocused();
  const outline = await last.evaluate((el) => getComputedStyle(el).outlineStyle);
  expect(outline).not.toBe("none");
});

test("controls answer hover, press and disabled states", async ({ page }) => {
  await mockTwitch(page);
  await page.goto("/");
  await enter(page, "states");
  await page.getByRole("button", { name: "Switch channel" }).click();
  const go = page.getByRole("button", { name: "Go" });
  await expect(go).toBeDisabled(); // nothing typed yet
  await page.getByPlaceholder("channel…").fill("not a name!");
  await expect(go).toBeDisabled();
  await page.getByPlaceholder("channel…").fill("valid_name");
  await expect(go).toBeEnabled();

  const seg = page.getByRole("radio", { name: "30s" }); // 1m is selected by default
  const before = await seg.evaluate((el) => getComputedStyle(el).color);
  await seg.hover();
  await expect.poll(() => seg.evaluate((el) => getComputedStyle(el).color)).not.toBe(before);
  // the sliding thumb follows the selection
  const thumb = page.locator(".seg-thumb");
  const x0 = (await thumb.boundingBox())!.x;
  await page.getByRole("radio", { name: "5m" }).click();
  await expect.poll(async () => (await thumb.boundingBox())!.x).toBeGreaterThan(x0 + 20);
});

test("hidden tab: counting continues but nothing re-renders until the tab is back", async ({ page }) => {
  let sock: { ws: WebSocketRoute; ch: string } | null = null;
  await mockTwitch(page, (ws, ch) => (sock = { ws, ch }));
  await page.goto("/");
  await enter(page, "background");
  await expect.poll(() => sock !== null).toBe(true);
  sock!.ws.send(line(sock!.ch, "first"));
  await expect(page.locator(".msg")).toHaveCount(1);

  const setHidden = (hidden: boolean) =>
    page.evaluate((h) => {
      Object.defineProperty(document, "hidden", { configurable: true, get: () => h });
      Object.defineProperty(document, "visibilityState", {
        configurable: true,
        get: () => (h ? "hidden" : "visible"),
      });
      document.dispatchEvent(new Event("visibilitychange"));
    }, hidden);

  await setHidden(true);
  for (let i = 0; i < 5; i++) sock!.ws.send(line(sock!.ch, "LMAO"));
  await page.waitForTimeout(2_000); // past a flush and a recount
  await expect(page.locator(".msg")).toHaveCount(1);
  await expect(page.locator(".cluster")).toHaveCount(0);

  await setHidden(false);
  await expect(page.locator(".msg")).toHaveCount(6);
  await expect(page.locator(".cluster")).toHaveCount(1, { timeout: 3_000 });
  await expect(page.locator(".cluster-n").first()).toHaveText("5");
});

test("the shell holds still while chat streams in (no layout shift of the zones)", async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  let sock: { ws: WebSocketRoute; ch: string } | null = null;
  await mockTwitch(page, (ws, ch) => (sock = { ws, ch }));
  await page.goto("/");
  await enter(page, "steady");
  await expect.poll(() => sock !== null).toBe(true);
  sock!.ws.send(line(sock!.ch, "hello"));
  await expect(page.locator(".msg")).toHaveCount(1);
  await page.waitForTimeout(500); // zone entrance done
  const boxes = () =>
    page.evaluate(() =>
      [".ws-head", ".zone-chat", ".zone-board", ".zone-pulse", ".board-head"].map((s) => {
        const r = document.querySelector(s)!.getBoundingClientRect();
        return [Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)];
      }),
    );
  const before = await boxes();
  const texts = ["LMAO", "dracula", "draconic", "what game is this?", "W", "insane", "KEKW"];
  for (let i = 0; i < 120; i++) sock!.ws.send(line(sock!.ch, texts[i % texts.length]));
  await expect.poll(() => page.locator(".cluster").count(), { timeout: 5_000 }).toBeGreaterThan(2);
  await page.waitForTimeout(1_600);
  expect(await boxes()).toEqual(before);
});

test("a group pushed off the board fades out where it stood, then is gone", async ({ page }) => {
  let sock: { ws: WebSocketRoute; ch: string } | null = null;
  await mockTwitch(page, (ws, ch) => (sock = { ws, ch }));
  await page.goto("/");
  await enter(page, "crowded");
  await expect.poll(() => sock !== null).toBe(true);
  const say = (text: string, n: number) => {
    for (let i = 0; i < n; i++) sock!.ws.send(line(sock!.ch, text));
  };
  // six one-word groups, 4..9 messages each: exactly a full board
  ["zorbo", "quixa", "plimb", "vrask", "gondu", "teflo"].forEach((w, i) => say(w, 4 + i));
  await expect(page.locator(".cluster")).toHaveCount(6, { timeout: 5_000 });
  await page.evaluate(() => {
    const w = window as unknown as { __ghosts: number };
    w.__ghosts = 0;
    new MutationObserver((records) => {
      for (const r of records)
        r.addedNodes.forEach((n) => {
          if (n instanceof HTMLElement && n.classList.contains("cluster-ghost")) w.__ghosts++;
        });
    }).observe(document.querySelector(".cluster-list")!, { childList: true });
  });
  say("mirsk", 12); // a seventh, bigger group takes a place; the smallest (zorbo) leaves the top six
  await expect(page.locator(".cluster-label").first()).toHaveText("mirsk", { timeout: 5_000 });
  await expect(page.locator(".cluster-label", { hasText: "zorbo" })).toHaveCount(0);
  expect(await page.evaluate(() => (window as unknown as { __ghosts: number }).__ghosts)).toBe(1);
  await expect(page.locator(".cluster-ghost")).toHaveCount(0, { timeout: 1_000 }); // cleaned up
  await expect(page.locator(".cluster")).toHaveCount(6);
  await expect(page.locator(".board-foot")).toContainText("+1 more");
});
