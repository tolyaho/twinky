import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import type { Plugin } from "vite";

// Transformers.js references ONNX Runtime's 27 MB wasm, so Vite copies it into the build — but at
// run time the worker loads it from jsDelivr (version-pinned by Transformers.js), and the copy is
// never requested. Leave it out of the deployment.
const dropUnusedWasm = (): Plugin => ({
  name: "drop-unused-ort-wasm",
  generateBundle(_, bundle) {
    for (const k of Object.keys(bundle)) if (k.endsWith(".wasm")) delete bundle[k];
  },
});

const ISOLATION = {
  "Cross-Origin-Opener-Policy": "same-origin",
  "Cross-Origin-Embedder-Policy": "credentialless",
};

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [react()],
  // The topic model runs threaded only on a cross-origin isolated page (SharedArrayBuffer).
  // `credentialless` keeps third-party subresources (fonts) loading; vercel.json sets the same.
  server: { headers: ISOLATION },
  preview: { headers: ISOLATION },
  worker: { format: "es", plugins: () => [dropUnusedWasm()] },
  build: {
    target: "es2021",
    sourcemap: false,
  },
  test: {
    environment: "jsdom",
    include: ["tests/unit/**/*.test.ts", "tests/unit/**/*.test.tsx"],
    globals: true,
  },
});
