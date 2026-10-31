// Candidate sentence encoders for the semantic-clustering evaluation, run with Transformers.js —
// the same runtime and the same ONNX weights the browser worker uses, so a quality number measured
// here is the quality a visitor gets. Pooling and prefixes are each model's own (read from the
// original repos' sentence-transformers configs), not guessed.
import { env, pipeline, type FeatureExtractionPipeline } from "@huggingface/transformers";
import { fileURLToPath } from "node:url";

env.cacheDir = fileURLToPath(new URL("./.models/", import.meta.url));

export interface Candidate {
  key: string;
  repo: string;
  /** onnx/<file>.onnx — omitted means the standard q8 `model_quantized.onnx`. */
  file?: string;
  pooling: "mean" | "cls";
  prefix?: string;
  mb: number; // download size of the ONNX weights, from the hub listing
  langs: "en" | "multi" | "en+ru";
}

export const CANDIDATES: Candidate[] = [
  { key: "minilm-l6", repo: "Xenova/all-MiniLM-L6-v2", pooling: "mean", mb: 23, langs: "en" },
  { key: "para-minilm-l3", repo: "Xenova/paraphrase-MiniLM-L3-v2", pooling: "mean", mb: 17, langs: "en" },
  { key: "bge-small", repo: "Xenova/bge-small-en-v1.5", pooling: "cls", mb: 34, langs: "en" },
  { key: "arctic-xs", repo: "Snowflake/snowflake-arctic-embed-xs", pooling: "cls", mb: 23, langs: "en" },
  { key: "mxbai-xsmall", repo: "mixedbread-ai/mxbai-embed-xsmall-v1", pooling: "mean", mb: 24, langs: "en" },
  { key: "rubert-tiny2", repo: "TrendHD/rubert-tiny2-int8", file: "rubert-tiny2-int8", pooling: "cls", mb: 29, langs: "en+ru" },
  { key: "user2-small", repo: "onnx-community/USER2-small-ONNX", pooling: "mean", prefix: "clustering: ", mb: 35, langs: "en+ru" },
  { key: "para-multi-l12", repo: "Xenova/paraphrase-multilingual-MiniLM-L12-v2", pooling: "mean", mb: 118, langs: "multi" },
  { key: "me5-small", repo: "Xenova/multilingual-e5-small", pooling: "mean", prefix: "query: ", mb: 118, langs: "multi" },
];

export interface Embedder {
  c: Candidate;
  embed(texts: string[]): Promise<Float32Array[]>;
  loadMs: number;
}

export async function load(c: Candidate): Promise<Embedder> {
  const t0 = performance.now();
  const extractor = (await pipeline("feature-extraction", c.repo, {
    dtype: c.file ? "fp32" : "q8",
    ...(c.file ? { model_file_name: c.file } : {}),
  } as never)) as FeatureExtractionPipeline;
  const loadMs = performance.now() - t0;
  return {
    c,
    loadMs,
    async embed(texts) {
      const out: Float32Array[] = [];
      for (let i = 0; i < texts.length; i += 64) {
        const batch = texts.slice(i, i + 64).map((t) => (c.prefix ?? "") + t);
        const t = await extractor(batch, { pooling: c.pooling, normalize: true });
        const dim = t.dims[1];
        const data = t.data as Float32Array;
        for (let r = 0; r < batch.length; r++) out.push(data.slice(r * dim, (r + 1) * dim));
      }
      return out;
    },
  };
}

export const cos = (a: Float32Array, b: Float32Array) => {
  let s = 0;
  for (let i = 0; i < a.length; i++) s += a[i] * b[i];
  return s;
};
