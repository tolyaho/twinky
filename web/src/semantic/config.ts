// What ships: the model and the grouping configuration, chosen on the dev split only
// (evals/semantic/README.md). The evaluation harness imports this same object, so the test
// number it reports is the configuration a visitor gets.
import { DEFAULT_OPTIONS, type HybridOptions } from "./hybrid";
import type { ModelSpec } from "./protocol";

/** all-MiniLM-L6-v2, 8-bit ONNX (Apache-2.0), pinned to the revision that was evaluated. */
export const MODEL: ModelSpec = {
  repo: "Xenova/all-MiniLM-L6-v2",
  revision: "751bff37182d3f1213fa05d7196b954e230abad9",
  pooling: "mean",
  mb: 23,
};

export const OPTIONS: HybridOptions = {
  ...DEFAULT_OPTIONS,
  method: "center",
  threshold: 0.65,
  minMessages: 2,
  minAuthors: 2,
  refine: 2,
  mergeCenters: false,
  lowinfoMin: 3,
  // the model reads English; other scripts group only when identical (no false merges from noise)
  script: "latin",
};

/** Share of wall time the model may use while catching up, so a phone's page never stalls. */
export const DUTY = 0.5;
