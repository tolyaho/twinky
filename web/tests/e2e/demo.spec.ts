import { test, expect, type Page } from "./fixtures";
import type { WebSocketRoute } from "./fixtures";

// A deterministic synthetic Twitch chat, injected by mocking the WebSocket server. This is a TEST
// FIXTURE ONLY — it never ships in the app, and it drives the exact same client code path a real
// Twitch socket does. (See spec §13: synthetic stream for repeatable browser tests.)
function line(text: string, i: number): string {
  const ts = Date.now();
  const name = `User${i}`;
  return (
    `@display-name=${name};id=e2e-${i}-${ts};room-id=1;tmi-sent-ts=${ts};user-type= ` +
    `:${name.toLowerCase()}!u@u.tmi.twitch.tv PRIVMSG #xqc :${text}`
  );
}

const SCRIPT: string[] = [
  ...Array.from({ length: 9 }, () => "LMAO"),
  ...["dracula", "draconic", "dracarys", "dracula", "draconic", "dracula"],
  ...["that was insane", "insane clutch", "actually insane", "insane"],
  ...["what game is this?", "whats the game", "what game is this"],
  ...["W", "W", "W stream", "first"],
];

async function scriptTwitch(page: Page) {
  await page.routeWebSocket(/irc-ws\.chat\.twitch\.tv/, (ws: WebSocketRoute) => {
    let started = false;
    ws.onMessage((msg) => {
      const s = typeof msg === "string" ? msg : msg.toString();
      if (s.startsWith("JOIN") && !started) {
        started = true;
        ws.send(":tmi.twitch.tv 366 justinfan1 #xqc :End of /NAMES list");
        SCRIPT.forEach((text, i) => {
          setTimeout(() => ws.send(line(text, i)), 150 + i * 55);
        });
      }
    });
  });
}

test("live flow: enter channel, cluster, inspect, switch", async ({ page }) => {
  await scriptTwitch(page);
  await page.goto("/");

  await expect(page.locator(".hero-title")).toBeVisible();
  await page.getByPlaceholder("enter a twitch channel").fill("xqc");
  await page.getByRole("button", { name: "Watch live" }).click();

  await expect(page.locator(".ws-channel-name")).toHaveText("#xqc");
  // messages arrive
  await expect(page.locator(".msg").first()).toBeVisible({ timeout: 10_000 });
  // clusters form (reaction + prefix + token at least)
  await expect(page.locator(".cluster")).not.toHaveCount(0, { timeout: 10_000 });
  await expect
    .poll(async () => page.locator(".cluster").count(), { timeout: 10_000 })
    .toBeGreaterThanOrEqual(2);

  // the workspace is one screen: the page never scrolls, and the newest message is in view
  const docOverflow = await page.evaluate(
    () => document.documentElement.scrollHeight - window.innerHeight,
  );
  expect(docOverflow).toBeLessThanOrEqual(0);
  await expect(page.locator(".msg").last()).toBeInViewport();

  await page.screenshot({ path: "screenshots/desktop-live.png", fullPage: false });

  // inspect a cluster -> its messages listed as evidence, and highlighted in the feed
  await page.locator(".cluster").first().click();
  await expect(page.locator(".cluster-sel")).toHaveCount(1);
  await expect(page.locator(".msg-lit").first()).toBeVisible({ timeout: 5_000 });
  const count = Number(await page.locator(".cluster-sel .cluster-n").textContent());
  await expect(page.locator(".evidence .ev")).toHaveCount(Math.min(count, 8));
  await page.getByRole("button", { name: "Close" }).click();
  await expect(page.locator(".evidence")).toHaveCount(0);
  await page.locator(".cluster").first().click();
  expect(await page.evaluate(() => window.scrollY)).toBe(0); // opening a group never scrolls the page
  await page.waitForTimeout(450); // let the open/reorder motion settle before the screenshot
  await page.screenshot({ path: "screenshots/desktop-selected.png", fullPage: false });

  // switch channel cleanly
  await page.getByRole("button", { name: "Switch channel" }).click();
  await page.getByPlaceholder("channel…").fill("hasanabi");
  await page.getByRole("button", { name: "Go" }).click();
  await expect(page.locator(".ws-channel-name")).toHaveText("#hasanabi");
});

test("replay flow is clearly labelled and clusters from real data", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("button", { name: /recorded example/i }).click();
  await expect(page.locator(".src-replay")).toBeVisible();
  await expect(page.getByText(/Replay\./)).toBeVisible();
  await expect(page.locator(".badge-replay")).toContainText(/Replay/);
  await expect
    .poll(async () => page.locator(".cluster").count(), { timeout: 15_000 })
    .toBeGreaterThanOrEqual(1);
  await page.screenshot({ path: "screenshots/desktop-replay.png", fullPage: false });
});

test("mobile: tabs switch between clusters, chat, pulse", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await scriptTwitch(page);
  await page.goto("/");
  await page.getByPlaceholder("enter a twitch channel").fill("xqc");
  await page.getByRole("button", { name: "Watch live" }).click();
  await expect(page.locator(".ws-channel-name")).toHaveText("#xqc");
  await expect(page.getByRole("tab", { name: "Clusters" })).toBeVisible();
  await expect.poll(async () => page.locator(".cluster").count(), { timeout: 10_000 }).toBeGreaterThan(1);
  // nothing in the workspace may overflow sideways on a phone
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth);
  expect(overflow).toBeLessThanOrEqual(0);
  await page.screenshot({ path: "screenshots/mobile-clusters.png", fullPage: false });
  await page.getByRole("tab", { name: "Chat" }).click();
  await expect(page.locator(".zone-chat")).toBeVisible();
  await page.screenshot({ path: "screenshots/mobile-chat.png", fullPage: false });
  await page.getByRole("tab", { name: "Pulse" }).click();
  await expect(page.locator(".zone-pulse")).toBeVisible();
  // the evidence is readable on a phone too, without the chat tab
  await page.getByRole("tab", { name: "Clusters" }).click();
  await page.locator(".cluster").first().click();
  await expect(page.locator(".evidence .ev").first()).toBeVisible();
  expect(
    await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth),
  ).toBeLessThanOrEqual(0);
  await page.waitForTimeout(450);
  await page.screenshot({ path: "screenshots/mobile-evidence.png", fullPage: false });
});

test("tablet: two columns, the board keeps the full height; chat and pulse stay reachable", async ({ page }) => {
  await page.setViewportSize({ width: 900, height: 1100 });
  await scriptTwitch(page);
  await page.goto("/");
  await page.getByPlaceholder("enter a twitch channel").fill("xqc");
  await page.getByRole("button", { name: "Watch live" }).click();
  await expect.poll(async () => page.locator(".cluster").count(), { timeout: 10_000 }).toBeGreaterThan(1);
  await expect(page.locator(".zone-pulse")).toBeInViewport();
  await expect(page.locator(".zone-chat")).toBeInViewport();
  await page.waitForTimeout(400);
  await page.screenshot({ path: "screenshots/tablet-live.png", fullPage: false });
});

test("quiet channel: connected but silent shows an honest state", async ({ page }) => {
  await page.routeWebSocket(/irc-ws\.chat\.twitch\.tv/, (ws) => {
    ws.onMessage((msg) => {
      const s = typeof msg === "string" ? msg : msg.toString();
      if (s.startsWith("JOIN")) ws.send(":tmi.twitch.tv 366 justinfan1 #xqc :End of /NAMES list");
      // never send any PRIVMSG -> quiet
    });
  });
  await page.goto("/");
  await page.getByPlaceholder("enter a twitch channel").fill("somequietchannel");
  await page.getByRole("button", { name: "Watch live" }).click();
  await expect(page.locator(".board-empty-title")).toBeVisible({ timeout: 20_000 });
  await expect(page.locator(".badge")).toContainText(/Quiet|Connected/, { timeout: 20_000 });
});

test("landing: tablet screenshot", async ({ page }) => {
  await page.setViewportSize({ width: 820, height: 1180 });
  await page.goto("/");
  await expect(page.locator(".hero-title")).toBeVisible();
  await page.screenshot({ path: "screenshots/tablet-landing.png", fullPage: true });
});

test("landing: desktop screenshot", async ({ page }) => {
  await page.setViewportSize({ width: 1280, height: 860 });
  await page.goto("/");
  await expect(page.locator(".hero-title")).toBeVisible();
  await page.screenshot({ path: "screenshots/desktop-landing.png", fullPage: true });
});

test("nonexistent channel: no JOIN acknowledgement shows Not found, not an endless spinner", async ({ page }) => {
  await page.routeWebSocket(/irc-ws\.chat\.twitch\.tv/, (ws) => {
    ws.onMessage(() => {
      /* Twitch sends nothing back for a channel that doesn't exist */
    });
  });
  await page.goto("/");
  await page.getByPlaceholder("enter a twitch channel").fill("zzqqnotarealchannel9871");
  await page.getByRole("button", { name: "Watch live" }).click();
  await expect(page.locator(".badge")).toContainText("Not found", { timeout: 15_000 });
  await expect(page.locator(".board-empty-title")).toHaveText("No such channel");
  await expect(page.locator(".feed-empty")).toContainText("no channel called #zzqqnotarealchannel9871");
  // a terminal state: nothing spins
  await expect(page.locator(".listening")).toHaveCount(0);
  await expect(page.locator(".dot-pulse")).toHaveCount(0);
  await expect(page.getByRole("button", { name: /Pause/ })).toHaveCount(0);
  // nothing is invented to fill the silence
  await expect(page.locator(".msg")).toHaveCount(0);
  await expect(page.locator(".cluster")).toHaveCount(0);
  await page.screenshot({ path: "screenshots/desktop-notfound.png" });
  await page.getByRole("button", { name: "Try another channel" }).click();
  await expect(page.getByPlaceholder("channel…")).toBeFocused();
});

test("window selector recounts and relabels; pause freezes the feed", async ({ page }) => {
  await scriptTwitch(page);
  await page.goto("/");
  await page.getByPlaceholder("enter a twitch channel").fill("xqc");
  await page.getByRole("button", { name: "Watch live" }).click();
  await expect.poll(async () => page.locator(".cluster").count(), { timeout: 10_000 }).toBeGreaterThan(0);

  await page.getByRole("radio", { name: "5m" }).click();
  await expect(page.getByRole("radio", { name: "5m" })).toHaveAttribute("aria-checked", "true");
  await expect(page.locator(".board-sub")).toContainText("5 minutes");
  await expect(page.locator(".pulse-sub")).toContainText("5 minutes");
  await expect(page.locator(".cluster-people").first()).toContainText(/\d+ (person|people)/);

  await page.getByRole("button", { name: /Pause/ }).click();
  const frozen = await page.locator(".msg").count();
  await page.waitForTimeout(800);
  expect(await page.locator(".msg").count()).toBe(frozen);
  await page.getByRole("button", { name: /Resume/ }).click();
  await page.screenshot({ path: "screenshots/desktop-5m.png" });
});
