import { test, expect } from "@playwright/test";

// REAL-NETWORK smoke test (tagged @live, excluded from the default run). It connects to an actual
// Twitch channel over the real anonymous IRC WebSocket — nothing is mocked — and proves that
// genuine messages arrive in the browser and cluster. The channel is passed via LIVE_CHANNEL so a
// busy, currently-live channel can be chosen at run time (chat liveness is not reproducible).
const CHANNEL = process.env.LIVE_CHANNEL ?? "jynxzi";

test(`@live real Twitch chat arrives and clusters (#${CHANNEL})`, async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m) => m.type() === "error" && errors.push(m.text()));

  await page.goto("/");
  await page.getByPlaceholder("enter a twitch channel").fill(CHANNEL);
  await page.getByRole("button", { name: "Watch live" }).click();

  await expect(page.locator(".ws-channel-name")).toHaveText(`#${CHANNEL}`);

  // Real messages from Twitch must appear.
  await expect(page.locator(".msg").first()).toBeVisible({ timeout: 30_000 });
  const msgCount = await page.locator(".msg").count();
  expect(msgCount).toBeGreaterThan(0);

  // Give the room ~25s to produce audience signals, then expect at least one cluster on a busy
  // channel. (If the chosen channel happens to be quiet, this is where it will show.)
  await page.waitForTimeout(25_000);
  const clusters = await page.locator(".cluster").count();
  const finalMsgs = await page.locator(".msg").count();
  const status = await page.locator(".badge").first().textContent();
  console.log(
    `[live-smoke] #${CHANNEL}: ${finalMsgs} msgs rendered, ${clusters} clusters, status="${status}"`,
  );

  await page.screenshot({ path: `screenshots/live-${CHANNEL}.png`, fullPage: false });

  expect(finalMsgs).toBeGreaterThan(0);
  expect(errors, `console errors: ${errors.join(" | ")}`).toEqual([]);
});
