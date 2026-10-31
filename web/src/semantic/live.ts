// The page side of grouping by meaning. Called synchronously on every board recount (~1.5 s), it
// never waits for the model: the deterministic groups (reactions, repeated phrases) are computed
// on the spot, the window's texts are handed to the worker, and topics come from the worker's
// latest answer, mapped onto the messages that are in the window now. Until the model has looked
// at a message it is counted as waiting, never as grouped.
import { isQuestion } from "../cluster/pulse";
import { lexicalGrouper } from "../engine/session";
import type { BoardRule, ChatEvent } from "../cluster/types";
import { fastGroups, textGroup, textItems, type HybridOptions, type Prepped, type SemGroup } from "./hybrid";
import { FAMILY_LABEL, prepare, type Family, type Prepared } from "./prep";
import type { FromWorker, ModelSpec, ToWorker, WireCluster, WireItem } from "./protocol";

export type SemanticState = "loading" | "ready" | "failed";

export interface SemanticInfo {
  state: SemanticState;
  /** messages with words in them that the model has not looked at yet */
  pending: number;
  /** messages with words in them in the window */
  textMessages: number;
  loadMs?: number;
  reason?: string;
}

export interface SemanticBoardGroup {
  key: string;
  rule: BoardRule;
  label: string;
  display: string;
  count: number;
  chatters: number;
  first_ts_ms: number;
  last_ts_ms: number;
  event_ids: string[];
  samples: string[];
}

export interface WorkerLike {
  postMessage(m: ToWorker): void;
  onmessage: ((e: MessageEvent<FromWorker>) => void) | null;
  onerror: ((e: ErrorEvent) => void) | null;
}

/** The most texts one recount hands to the model: repeated texts first, then the newest. */
export const MAX_ITEMS = 400;

// One worker per page, shared by every session: the model loads once, and a channel switch is a
// new epoch, not a new download.
interface Link {
  worker: WorkerLike;
  listeners: Set<(m: FromWorker) => void>;
  last: FromWorker | null;
}
let shared: Link | null = null;
let epochs = 0;

function connect(make: () => WorkerLike, spec: ModelSpec, duty: number): Link {
  if (shared) return shared;
  const worker = make();
  const s: Link = { worker, listeners: new Set(), last: null };
  worker.onmessage = (e) => {
    if (e.data.type !== "result") s.last = e.data;
    for (const l of s.listeners) l(e.data);
  };
  worker.onerror = (e) => {
    const m: FromWorker = { type: "failed", reason: e.message || "the topic worker stopped" };
    s.last = m;
    for (const l of s.listeners) l(m);
  };
  worker.postMessage({ type: "init", spec, device: "wasm", duty });
  shared = s;
  return s;
}

/** Tests only: forget the shared worker. */
export function resetSharedWorker(): void {
  shared = null;
}

interface Topic {
  id: string;
  keys: Set<string>;
  labelKey: string;
}

export class SemanticGrouper {
  readonly epoch = ++epochs;
  state: SemanticState = "loading";
  private loadMs?: number;
  private reason?: string;
  private readonly link: Link;
  private readonly prep = new Map<string, Prepared>();
  private seq = 0;
  private sentSig = "";
  private answered = new Set<string>(); // texts of the last answered request
  private waiting = new Set<string>(); // ... of which these had no vector yet
  private clusters: WireCluster[] = [];
  private topics: Topic[] = [];
  private nextTopic = 0;
  private readonly onMessage = (m: FromWorker) => this.receive(m);

  constructor(
    private readonly channel: string,
    spec: ModelSpec,
    private readonly options: HybridOptions,
    make: () => WorkerLike,
    duty = 1,
  ) {
    this.link = connect(make, spec, duty);
    this.link.listeners.add(this.onMessage);
    this.link.worker.postMessage({ type: "reset", epoch: this.epoch });
    if (this.link.last) this.receive(this.link.last); // the model may already be loaded
  }

  stop(): void {
    this.link.listeners.delete(this.onMessage);
  }

  info(textMessages: number, pending: number): SemanticInfo {
    return { state: this.state, pending, textMessages, loadMs: this.loadMs, reason: this.reason };
  }

  private receive(m: FromWorker) {
    if (m.type === "ready") {
      this.state = "ready";
      this.loadMs = m.loadMs;
    } else if (m.type === "failed") {
      this.state = "failed";
      this.reason = m.reason;
    } else if (m.epoch === this.epoch) {
      // a result for an earlier channel carries an older epoch and is ignored here
      this.clusters = m.clusters;
      this.waiting = new Set(m.waiting);
      this.answered = this.requested.get(m.seq) ?? this.answered;
      for (const s of [...this.requested.keys()]) if (s <= m.seq) this.requested.delete(s);
    }
  }
  private requested = new Map<number, Set<string>>();

  /** One recount of the window. Never blocks on the model. */
  group(window: readonly ChatEvent[]): { groups: SemanticBoardGroup[]; soloMessages: number; semantic: SemanticInfo } {
    if (this.state === "failed") {
      // the model could not run: the word rules, exactly as before topics existed, said so plainly
      const r = lexicalGrouper.group(window);
      return { ...r, semantic: this.info(0, 0) };
    }
    const prepped: Prepped[] = window.map((e) => {
      let p = this.prep.get(e.id);
      if (!p) this.prep.set(e.id, (p = prepare(e.text, this.channel, e.bot)));
      return { id: e.id, author: e.author, text: e.text, prep: p };
    });
    if (this.prep.size > window.length * 2 + 1_000) {
      const live = new Set(window.map((e) => e.id));
      for (const id of this.prep.keys()) if (!live.has(id)) this.prep.delete(id);
    }
    const byId = new Map(window.map((e) => [e.id, e]));
    const items = textItems(prepped, this.options);

    // hand the model what it should look at, most-repeated first, then newest
    const order = [...items.values()].sort(
      (a, b) => b.ids.length - a.ids.length || (byId.get(b.ids.at(-1)!)!.ts_ms - byId.get(a.ids.at(-1)!)!.ts_ms),
    );
    const wire: WireItem[] = order.slice(0, MAX_ITEMS).map((t) => ({ key: t.key, weight: t.ids.length, authors: [...t.authors] }));
    const sig = `${window.length}:${window.at(-1)?.id ?? ""}`;
    if (sig !== this.sentSig) {
      this.sentSig = sig;
      const seq = ++this.seq;
      this.requested.set(seq, new Set(wire.map((w) => w.key)));
      if (this.requested.size > 8) this.requested.delete(this.requested.keys().next().value as number);
      this.link.worker.postMessage({ type: "work", epoch: this.epoch, seq, items: wire, options: this.options });
    }

    const sem: SemGroup[] = fastGroups(prepped, this.options);
    const placed = new Set<string>();
    if (this.state === "ready") {
      for (const c of this.clusters) {
        const g = textGroup(c.keys, items, c.coherence);
        if (g && g.ids.length >= this.options.minMessages && g.authors >= this.options.minAuthors) {
          sem.push(g);
          for (const k of g.texts) placed.add(k);
        }
      }
    }

    let pending = 0, textMessages = 0;
    for (const t of items.values()) {
      textMessages += t.ids.length;
      if (this.state === "ready" && this.answered.has(t.key) && !this.waiting.has(t.key)) continue;
      pending += t.ids.length;
      // the same words from several chatters need no model: shown at once, as a repeat, until the
      // model has read them (and may put them in a topic)
      if (!placed.has(t.key) && t.ids.length >= this.options.minMessages && t.authors.size >= this.options.minAuthors)
        sem.push(textGroup([t.key], items)!);
    }

    // one person repeating themselves is not the room
    let soloMessages = 0;
    const solo = new Map<string, Set<string>>();
    const soloN = new Map<string, number>();
    for (const m of prepped) {
      const k = m.prep.kind === "reaction" ? `r:${m.prep.family}` : m.prep.kind === "skip" ? null : `k:${m.prep.key}`;
      if (!k) continue;
      (solo.get(k) ?? solo.set(k, new Set()).get(k)!).add(m.author);
      soloN.set(k, (soloN.get(k) ?? 0) + 1);
    }
    for (const [k, a] of solo) if (a.size === 1 && soloN.get(k)! >= 2) soloMessages += soloN.get(k)!;

    return {
      groups: this.toBoard(sem, byId),
      soloMessages,
      semantic: this.info(textMessages, pending),
    };
  }

  /** Board rows, with topic identity and labels carried over from the previous recount. */
  private toBoard(sem: SemGroup[], byId: ReadonlyMap<string, ChatEvent>): SemanticBoardGroup[] {
    const claimed = new Set<string>();
    const nextTopics: Topic[] = [];
    const out: SemanticBoardGroup[] = [];
    sem.sort((a, b) => b.ids.length - a.ids.length || (a.key < b.key ? -1 : 1));
    for (const g of sem) {
      const ids = [...g.ids].sort((a, b) => byId.get(a)!.ts_ms - byId.get(b)!.ts_ms || (a < b ? -1 : 1));
      const events = ids.map((id) => byId.get(id)!);
      let key = g.key, rule: BoardRule, display: string, samples: string[];
      if (g.kind === "reaction") {
        rule = "reaction";
        const fam = g.family!;
        display = fam.startsWith("emote:") ? commonest(events.map((e) => firstWord(e.text))) : FAMILY_LABEL[fam as Family];
        samples = distinct(events.map((e) => e.text.trim()).reverse());
      } else if (g.kind === "phrase") {
        rule = "phrase";
        display = commonest(events.map((e) => tidy(e.text)));
        samples = [display];
      } else {
        const keys = new Set(g.texts);
        // the earlier topic sharing the most texts with this one keeps its identity
        let best: Topic | null = null, overlap = 0;
        for (const t of this.topics) {
          if (claimed.has(t.id)) continue;
          let n = 0;
          for (const k of t.keys) if (keys.has(k)) n++;
          if (n > overlap) (best = t), (overlap = n);
        }
        const id = best ? best.id : `t${++this.nextTopic}`;
        claimed.add(id);
        // the label changes only if its text left the group or another text clearly outweighs it
        const weight = (k: string) => g.ids.filter((x) => (this.prep.get(x)?.key ?? "") === k).length;
        let labelKey = g.texts[0];
        if (best && keys.has(best.labelKey) && weight(g.texts[0]) < 1.5 * weight(best.labelKey)) labelKey = best.labelKey;
        nextTopics.push({ id, keys, labelKey });
        key = `t:${id}`;
        const asked = events.filter((e) => isQuestion(e.text)).length;
        // one word in several spellings ("amethyst", "Amethysts") is the same answer repeated,
        // not a discussion: say so rather than call it a topic
        rule = sameWordVariants(g.texts) ? "phrase" : asked * 2 >= events.length ? "question" : "topic";
        const textOf = (k: string) => tidy(events.filter((e) => this.prep.get(e.id)?.key === k).at(-1)?.text ?? k);
        display = shorten(textOf(labelKey));
        // the row's sample is a different wording: the point of a topic is that they differ
        samples = g.texts.filter((k) => k !== labelKey).map(textOf);
        if (!samples.length) samples = [display];
      }
      out.push({
        key,
        rule,
        label: display,
        display,
        count: ids.length,
        chatters: new Set(events.map((e) => e.author)).size,
        first_ts_ms: events[0].ts_ms,
        last_ts_ms: events[events.length - 1].ts_ms,
        event_ids: ids,
        samples: samples.slice(0, 3),
      });
    }
    this.topics = nextTopics;
    return out;
  }
}

/** Every text is a single word, and they all start with the same four letters. */
export function sameWordVariants(texts: readonly string[]): boolean {
  if (texts.length < 2 || texts.some((t) => t.includes(" "))) return false;
  const stem = Array.from(texts[0]).slice(0, 4).join("");
  return Array.from(stem).length === 4 && texts.every((t) => t.startsWith(stem));
}

const MENTION_LEAD = /^(?:@\w+[\s,:]*)+/;
/** A message as a label: leading @mentions and runs of whitespace removed. */
function tidy(t: string): string {
  return t.replace(MENTION_LEAD, "").replace(/\s+/g, " ").trim() || t.trim();
}
function firstWord(t: string): string {
  return t.trim().split(/\s+/)[0] ?? t;
}
/** At most eight words — a label, not a paragraph. The full message is in the evidence. */
function shorten(t: string): string {
  const w = t.split(" ");
  return w.length <= 8 ? t : `${w.slice(0, 8).join(" ")}…`;
}
function commonest(xs: string[]): string {
  const n = new Map<string, number>();
  for (const x of xs) n.set(x, (n.get(x) ?? 0) + 1);
  let best = xs[0] ?? "", bn = 0;
  for (const [x, k] of n) if (k > bn || (k === bn && x < best)) (best = x), (bn = k);
  return best;
}
function distinct(xs: string[]): string[] {
  return [...new Set(xs)];
}
