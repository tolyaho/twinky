// The hybrid grouping of one window of chat: the deterministic fast path (prep.ts) for reactions,
// commands and bare repeats, and grouping by meaning (cluster.ts) for messages that carry words.
// Vectors come from outside — the browser worker or the evaluation harness — so this is a pure
// function of (messages, vectors, options) and both run the identical code.
import { clusterItems, coherence, type ClusterOptions, type Item } from "./cluster";
import { prepare, type Prepared } from "./prep";

export interface Msg {
  id: string;
  author: string;
  text: string;
  bot?: boolean;
  /** words Twitch marked as emotes (live chat only; the evaluation's captures have none) */
  emotes?: readonly string[];
}

export type SemKind =
  | "reaction" // one family of reaction (laughing, hype, …) or one emote nobody knows the meaning of
  | "phrase" // the same words from several chatters: copypasta, a repeated command, a vote
  | "topic"; // different words, one meaning — the only kind that needs a model

export interface SemGroup {
  /** Stable within a window: `r:laughing`, `p:<text>`, `t:<medoid text>`. */
  key: string;
  kind: SemKind;
  family?: string;
  ids: string[];
  /** phrase/topic: distinct texts in the group, most frequent first (the first is the medoid) */
  texts: string[];
  authors: number;
  /** topic: mean similarity of the group's messages to its center */
  coherence?: number;
}

export interface HybridOptions extends ClusterOptions {
  /** identical bare numbers / one-word replies / commands need this many messages to be a vote */
  lowinfoMin: number;
  /**
   * Which texts the model is shown. "latin": an English-only model never sees text that is
   * mostly in another script (it would compare noise and merge unrelated messages); such text
   * groups only when identical, exactly as without a model.
   */
  script?: "latin" | "any";
  /**
   * A group made only of one-word messages keeps together only the spellings of one word (the
   * same first four letters). One word gives the model too little to compare meaning: what it
   * compares is spelling, so "amethyst" joins "americna" and "ranked" joins "ranger" — guesses in
   * a word game, an emote it does not know, not one thing being said. (evals/semantic/followup.md)
   */
  oneWordStems?: boolean;
  /** leave "chat" / "chatter(s)" out of what the model compares (src/semantic/prep.ts) */
  vocatives?: boolean;
}

const stem = (word: string) => Array.from(word).slice(0, 4).join("");

/**
 * One cluster of texts as the groups it stands for. With `oneWordStems`, a cluster of one-word
 * texts is split by stem; anything with a phrase in it is left as the model made it.
 */
export function splitCluster(keys: readonly string[], o: Pick<HybridOptions, "oneWordStems">): string[][] {
  if (!o.oneWordStems || keys.length < 2 || keys.some((k) => k.includes(" "))) return [[...keys]];
  const by = new Map<string, string[]>();
  for (const k of keys) (by.get(stem(k)) ?? by.set(stem(k), []).get(stem(k))!).push(k);
  return [...by.values()];
}

/** Whether the model should see this text, given the script it was trained on. */
export function embeddable(key: string, o: Pick<HybridOptions, "script">): boolean {
  if (o.script !== "latin") return true;
  const letters = key.match(/\p{L}/gu)?.length ?? 0;
  const latin = key.match(/\p{Script=Latin}/gu)?.length ?? 0;
  return letters === 0 || latin * 2 >= letters;
}

export const DEFAULT_OPTIONS: HybridOptions = {
  method: "center",
  threshold: 0.6,
  minMessages: 2,
  minAuthors: 2,
  refine: 2,
  lowinfoMin: 3,
  script: "any",
};

export interface Prepped extends Msg {
  prep: Prepared;
}

export function prepAll(msgs: readonly Msg[], channel: string, o: Pick<HybridOptions, "vocatives"> = {}): Prepped[] {
  return msgs.map((m) => ({
    ...m,
    prep: prepare(m.text, channel, m.bot, { vocatives: o.vocatives, emotes: m.emotes ? new Set(m.emotes) : undefined }),
  }));
}

/** The texts the model has to embed for these messages: unique, in first-seen order. */
export function textsToEmbed(prepped: readonly Prepped[], o: Pick<HybridOptions, "script"> = {}): string[] {
  return [...textItems(prepped, o).keys()];
}

const authorCount = (ids: readonly string[], byId: ReadonlyMap<string, Prepped>) =>
  new Set(ids.map((id) => byId.get(id)!.author)).size;

/** Stage B: reactions by family; identical commands and bare repeats by their text. */
export function fastGroups(prepped: readonly Prepped[], o: HybridOptions): SemGroup[] {
  const byId = new Map(prepped.map((m) => [m.id, m]));
  const buckets = new Map<string, { kind: SemKind; family?: string; ids: string[]; min: number; text: string }>();
  for (const m of prepped) {
    const p = m.prep;
    const verbatim = p.kind === "text" && !embeddable(p.key, o); // the model can't read it
    const k =
      p.kind === "reaction" ? `r:${p.family}` : p.kind === "command" || p.kind === "lowinfo" || verbatim ? `p:${p.key}` : null;
    if (!k) continue;
    let b = buckets.get(k);
    if (!b) {
      b = p.kind === "reaction"
        ? { kind: "reaction", family: p.family, ids: [], min: 2, text: "" }
        : { kind: "phrase", ids: [], min: verbatim ? 2 : o.lowinfoMin, text: p.key };
      buckets.set(k, b);
    }
    b.ids.push(m.id);
  }
  const out: SemGroup[] = [];
  for (const [key, b] of buckets) {
    const authors = authorCount(b.ids, byId);
    if (b.ids.length >= b.min && authors >= o.minAuthors)
      out.push({ key, kind: b.kind, family: b.family, ids: b.ids, texts: b.text ? [b.text] : [], authors });
  }
  return out;
}

export interface TextItem {
  key: string;
  ids: string[];
  authors: Set<string>;
}

/** Messages the model groups, one entry per distinct text (what is embedded), first-seen order. */
export function textItems(prepped: readonly Prepped[], o: Pick<HybridOptions, "script"> = {}): Map<string, TextItem> {
  const out = new Map<string, TextItem>();
  for (const m of prepped) {
    if (m.prep.kind !== "text" || !m.prep.key || !embeddable(m.prep.key, o)) continue;
    let t = out.get(m.prep.key);
    if (!t) out.set(m.prep.key, (t = { key: m.prep.key, ids: [], authors: new Set() }));
    t.ids.push(m.id);
    t.authors.add(m.author);
  }
  return out;
}

/** A group of distinct texts, as clustered, turned back into messages of this window. */
export function textGroup(keys: readonly string[], items: ReadonlyMap<string, TextItem>, coh?: number): SemGroup | null {
  const members = keys
    .map((k) => items.get(k))
    .filter((t): t is TextItem => t !== undefined)
    .sort((a, b) => b.ids.length - a.ids.length || (a.key < b.key ? -1 : 1));
  if (!members.length) return null;
  const authors = new Set<string>();
  for (const t of members) for (const a of t.authors) authors.add(a);
  const kind: SemKind = members.length === 1 ? "phrase" : "topic";
  return {
    key: `${kind === "phrase" ? "p" : "t"}:${members[0].key}`,
    kind,
    ids: members.flatMap((t) => t.ids),
    texts: members.map((t) => t.key),
    authors: authors.size,
    coherence: kind === "topic" ? coh : undefined,
  };
}

export interface HybridResult {
  groups: SemGroup[];
  /** text messages whose vector was not available yet: not grouped, and not counted as covered */
  pending: number;
  /** text messages in the window (the denominator for `pending`) */
  textMessages: number;
}

/** The whole hybrid grouping of a window, given the vectors (evaluation and tests). */
export function hybridGroups(
  prepped: readonly Prepped[],
  vectorOf: (text: string) => Float32Array | undefined,
  o: HybridOptions = DEFAULT_OPTIONS,
): HybridResult {
  const groups = fastGroups(prepped, o);
  const texts = textItems(prepped, o);
  const items: Item[] = [];
  let pending = 0, textMessages = 0;
  for (const t of texts.values()) {
    textMessages += t.ids.length;
    const vec = vectorOf(t.key);
    if (!vec) pending += t.ids.length;
    else items.push({ key: t.key, vec, weight: t.ids.length, authors: t.authors });
  }
  for (const g of clusterItems(items, o)) {
    for (const keys of splitCluster(g.map((i) => items[i].key), o)) {
      const sg = textGroup(keys, texts, coherence(items, g));
      if (sg && sg.ids.length >= o.minMessages && sg.authors >= o.minAuthors) groups.push(sg);
    }
  }
  groups.sort((a, b) => b.ids.length - a.ids.length || (a.key < b.key ? -1 : 1));
  return { groups, pending, textMessages };
}
