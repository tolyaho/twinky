// Browser benchmark of the semantic worker: real Chromium and WebKit (Playwright), the real worker
// code, the real model download. Cold = a fresh browser profile (nothing cached); warm = the same
// profile again (weights from the browser cache). Texts are the distinct texts of the dev windows.
//
//   npx tsx web/eval/browser-bench.ts [models] [browsers]     e.g.  minilm-l6,user2-small chromium,webkit
import { execSync } from "node:child_process";
import { chromium, webkit, type BrowserType } from "@playwright/test";
import { createServer } from "vite";
import type { ModelSpec } from "../src/semantic/protocol";
import { hybridTexts } from "./arms";
import { checkFrozen, realWindows } from "./data";
import { CANDIDATES } from "./embedders";

const REVISIONS: Record<string, string> = {
  "minilm-l6": "751bff37182d3f1213fa05d7196b954e230abad9",
  "user2-small": "4a3caf0c13a10330815441c2408b7b9447f23744",
  "me5-small": "761b726dd34fb83930e26aab4e9ac3899aa1fa78",
  "mxbai-xsmall": "e6ac24e5d6efb8782b59de1647b3ececb4ece94e",
};
const [models = "minilm-l6,user2-small", browsers = "chromium"] = process.argv.slice(2);

checkFrozen();
const texts = [...new Set(realWindows().filter((w) => w.split === "dev").flatMap(hybridTexts))].slice(0, 400);

// ISOLATE=1 serves the page cross-origin isolated (COOP/COEP), which lets ONNX Runtime use threads
const isolate = process.env.ISOLATE === "1";
const server = await createServer({
  root: new URL("..", import.meta.url).pathname,
  server: {
    port: 5199,
    strictPort: true,
    headers: isolate ? { "Cross-Origin-Opener-Policy": "same-origin", "Cross-Origin-Embedder-Policy": "credentialless" } : {},
  },
  optimizeDeps: { include: ["@huggingface/transformers"] },
  logLevel: "error",
});
await server.listen();
const url = `http://localhost:5199/eval/bench/index.html?duty=${process.env.DUTY ?? "1"}`;
{
  // first load makes Vite pre-bundle dependencies (and reload); do it before anything is timed
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.goto(url);
  await p.waitForTimeout(4_000);
  await b.close();
}

/** Resident memory of every process of the launched browser, in MB (macOS/Linux `ps`). */
function browserRssMB(marker: string): number {
  const out = execSync("ps -axo rss=,command=").toString();
  return Math.round(out.split("\n").filter((l) => l.includes(marker)).reduce((s, l) => s + Number(l.trim().split(/\s+/)[0] || 0), 0) / 1024);
}

const rows: Record<string, unknown>[] = [];
for (const bname of browsers.split(",")) {
  const type: BrowserType = bname === "webkit" ? webkit : chromium;
  for (const key of models.split(",")) {
    const c = CANDIDATES.find((x) => x.key === key)!;
    const spec: ModelSpec = { repo: c.repo, revision: REVISIONS[key] ?? "main", pooling: c.pooling, prefix: c.prefix, mb: c.mb };
    const browser = await type.launch();
    const marker = bname === "webkit" ? "ms-playwright/webkit" : "ms-playwright/chromium";
    const ctx = await browser.newContext();
    for (const phase of ["cold", "warm"]) {
      const page = await ctx.newPage();
      const bytes = { n: 0 };
      page.on("response", async (r) => {
        const len = Number((await r.allHeaders())["content-length"] ?? 0);
        if (/huggingface|hf\.co|jsdelivr|xethub/.test(r.url())) bytes.n += len;
      });
      await page.goto(url);
      await page.waitForFunction(() => typeof window.bench === "function", null, { timeout: 30_000 });
      const before = browserRssMB(marker);
      try {
        const res = await page.evaluate(([s, t]) => window.bench(s, t), [spec, texts] as const);
        rows.push({ browser: bname, isolated: isolate, duty: process.env.DUTY ?? "1", model: key, phase, ...res, transferMB: +(bytes.n / 1e6).toFixed(1), rssDeltaMB: browserRssMB(marker) - before });
      } catch (e) {
        rows.push({ browser: bname, model: key, phase, error: String(e).slice(0, 120) });
      }
      await page.close();
    }
    await browser.close();
  }
}
await server.close();
console.table(rows);
console.log(`machine: ${execSync("sysctl -n machdep.cpu.brand_string 2>/dev/null || uname -m").toString().trim()}`);
