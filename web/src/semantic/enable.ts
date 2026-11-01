// Whether this visit groups by meaning, and the grouper that does it. The model is loaded only
// when a channel is opened (never by the landing page, so a crawler costs nothing), and never at
// all when the visitor asked for less data, the browser cannot run workers or WebAssembly, or the
// page was opened with `?topics=off` (the word-rules board, kept as baseline and fallback).
import type { Grouper } from "../engine/session";
import { DUTY, MODEL, OPTIONS } from "./config";
import { SemanticGrouper, type WorkerLike } from "./live";

export function topicsEnabled(): boolean {
  if (typeof window === "undefined" || typeof Worker === "undefined" || typeof WebAssembly === "undefined") return false;
  if (new URLSearchParams(window.location.search).get("topics") === "off") return false;
  const conn = (navigator as Navigator & { connection?: { saveData?: boolean } }).connection;
  return !conn?.saveData;
}

const makeWorker = (): WorkerLike =>
  new Worker(new URL("./worker.ts", import.meta.url), { type: "module" }) as unknown as WorkerLike;

export function makeGrouper(channel: string): Grouper | undefined {
  if (!topicsEnabled()) return undefined;
  return new SemanticGrouper(channel, MODEL, OPTIONS, makeWorker, DUTY);
}

/**
 * The overlay's grouper. It never shows the word rules' shared-word groups on stream: with the
 * model it groups by meaning, and without it (`topics=off`, a browser that cannot run it, or a
 * model that failed) it shows reactions and exact repeats only — the part that needs no model.
 */
export function makeOverlayGrouper(channel: string): Grouper {
  return new SemanticGrouper(channel, MODEL, OPTIONS, topicsEnabled() ? makeWorker : null, DUTY, "repeats");
}
