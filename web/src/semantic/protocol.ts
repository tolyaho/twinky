// Messages between the page and the semantic worker. Every work request and result carries the
// session's epoch: a result from a previous channel (or a previous window setting) is dropped on
// arrival, so it can never land in the wrong chat.
import type { ClusterOptions } from "./cluster";

export interface ModelSpec {
  repo: string;
  /** a pinned commit of the model repo, so the weights a visitor gets are the weights evaluated */
  revision: string;
  pooling: "mean" | "cls";
  prefix?: string;
  /** download size of the quantised weights, for the honest "loading" note */
  mb: number;
}

export interface WireItem {
  key: string; // the normalised text that is embedded
  weight: number; // messages carrying it
  authors: string[]; // pseudonymous chatters who sent it
}

export type ToWorker =
  | {
      type: "init";
      spec: ModelSpec;
      device: "auto" | "wasm";
      /** share of wall time the model may use while catching up on a backlog (default 1) */
      duty?: number;
    }
  | { type: "work"; epoch: number; seq: number; items: WireItem[]; options: ClusterOptions }
  | { type: "reset"; epoch: number };

export interface WireCluster {
  keys: string[];
  coherence: number;
}

export type FromWorker =
  | { type: "ready"; device: "webgpu" | "wasm"; loadMs: number }
  | { type: "failed"; reason: string }
  | {
      type: "result";
      epoch: number;
      seq: number;
      clusters: WireCluster[];
      /** texts of this request still waiting for a vector after this round */
      waiting: string[];
      embedMs: number;
      clusterMs: number;
    };
