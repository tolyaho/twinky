import { test as base, type BrowserContext } from "@playwright/test";
import { existsSync, readFileSync } from "node:fs";
import { extname, join } from "node:path";
import { fileURLToPath } from "node:url";

// The topic model in the browser tests. A visitor's browser downloads it from the Hugging Face hub
// (pinned revision) and ONNX Runtime's WebAssembly from jsDelivr; here both are served from disk
// when they are there — the weights the evaluation downloaded into eval/.models, and the runtime
// npm installed — so a run does not depend on two CDNs and is not slowed by a 30 MB download.
// Anything not on disk goes to the network as usual. `topicModel: "broken"` makes the hub fail,
// to test what a visitor sees when the model cannot load.
//
// TEST FIXTURE ONLY: the deployed page never serves the model itself.

const WEB = fileURLToPath(new URL("../../", import.meta.url));
const MODELS = join(WEB, "eval/.models");
const ORT = join(WEB, "node_modules/onnxruntime-web");
const ORT_VERSION: string = existsSync(join(ORT, "package.json"))
  ? JSON.parse(readFileSync(join(ORT, "package.json"), "utf8")).version
  : "";

const TYPES: Record<string, string> = {
  ".json": "application/json",
  ".onnx": "application/octet-stream",
  ".wasm": "application/wasm",
  ".mjs": "text/javascript",
};

export type TopicModel = "local" | "network" | "broken";

/** Files this test process served from disk (to check the worker's requests were intercepted). */
export const served: string[] = [];

async function serveTopicModel(context: BrowserContext, mode: TopicModel, delayMs: number) {
  if (mode === "network") return;
  await context.route(/^https:\/\/huggingface\.co\/([^/]+\/[^/]+)\/resolve\/[^/]+\/([^?]+)/, async (route) => {
    if (delayMs) await new Promise((r) => setTimeout(r, delayMs));
    if (mode === "broken") return route.fulfill({ status: 503, body: "unavailable" }).catch(() => {});
    const [, repo, file] = /^https:\/\/huggingface\.co\/([^/]+\/[^/]+)\/resolve\/[^/]+\/([^?]+)/.exec(route.request().url())!;
    const path = join(MODELS, repo, file);
    if (!existsSync(path)) return route.continue();
    served.push(`${repo}/${file}`);
    await route.fulfill({
      status: 200,
      body: readFileSync(path),
      headers: { "content-type": TYPES[extname(path)] ?? "application/octet-stream", "access-control-allow-origin": "*" },
    });
  });
  await context.route(/^https:\/\/cdn\.jsdelivr\.net\/npm\/onnxruntime-web@([^/]+)\/dist\/([^?]+)/, async (route) => {
    const [, version, file] = /^https:\/\/cdn\.jsdelivr\.net\/npm\/onnxruntime-web@([^/]+)\/dist\/([^?]+)/.exec(route.request().url())!;
    const path = join(ORT, "dist", file);
    if (version !== ORT_VERSION || !existsSync(path)) return route.continue();
    served.push(`onnxruntime-web/${file}`);
    await route.fulfill({
      status: 200,
      body: readFileSync(path),
      headers: { "content-type": TYPES[extname(path)] ?? "application/octet-stream", "access-control-allow-origin": "*" },
    });
  });
}

export const test = base.extend<{ topicModel: TopicModel; topicModelDelayMs: number }>({
  topicModel: ["local", { option: true }],
  topicModelDelayMs: [0, { option: true }],
  context: async ({ context, topicModel, topicModelDelayMs }, use) => {
    await serveTopicModel(context, topicModel, topicModelDelayMs);
    await use(context);
  },
});

export { expect } from "@playwright/test";
export type { Page, WebSocketRoute } from "@playwright/test";
