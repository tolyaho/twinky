// Faithful port of the grouping half of `src/ts/workflow/reduce.py`: `group_chat`,
// `grouped_summary`, `is_reaction`, `_tokens`, `_pick`. Three deterministic rules applied in a
// fixed order; a message lands in exactly one group, so counts sum and nothing is double-counted.
import { canonical } from "./canonical";
import type { ChatEvent, Group, GroupRule, GroupedSummary } from "./types";

export const EMPTY_KEY = "∅";
export const REACTION_KEY = "∎reaction";
export const REACTION_LABEL = "reaction wave";

// Laughter, after `canonical` has folded the repeats ("AHAHAHAHA" -> "ahaha"). Anchored: "lol"
// inside a sentence is a sentence, not a reaction.
const LAUGHTER =
  /^(?:l+o+l+(?:ol)*|lmf?ao|rofl|kekw?|xd+|(?:a?ha){2,}h?|(?:he){2,}|(?:а?ха){2,}х?|(?:хе){2,})$/u;
const WORDISH = /[0-9A-Za-zÀ-ɏЀ-ӿ]/u;

// Deliberately small and frozen — a long list encodes opinions a model-free rule cannot defend.
// Copied verbatim from reduce.py STOPWORDS.
export const STOPWORDS: ReadonlySet<string> = new Set(
  `a an and are as at be been but by can cant did do does dont for from get got had has have he her
him his how i if in is it its just like me my no not now of on one or our out she should so some
than that the their them then there these they this to too up us very was we were what when where
which who why will with would you your yours yeah yes yep nah nope ok okay omg pls plz thanks
bro bruh man dude guys chat stream streamer twitch`
    .split(/\s+/)
    .filter(Boolean),
);

const MIN_PREFIX_LEN = 4; // the prefix a single-word message is bucketed by
const MIN_PREFIX_GROUP = 4; // a prefix is a signal at four messages, not two
const MIN_TOKEN_GROUP = 3; // a shared rare token is a signal at three

// Python `len()` and slicing work on code points; JS strings are UTF-16. Use these so an emoji
// (astral) is one unit, exactly as Python counts it.
const cps = (s: string): string[] => Array.from(s);
const cplen = (s: string): number => cps(s).length;
const cpslice = (s: string, a: number, b?: number): string => cps(s).slice(a, b).join("");

/** Laughter or symbols-only. Both are real audience volume and neither is a topic. */
export function isReaction(canon: string): boolean {
  if (!canon || canon === EMPTY_KEY) return false;
  if (LAUGHTER.test(canon.replace(/ /g, ""))) return true;
  return !WORDISH.test(canon); // emote-only: symbols, no letters or digits
}

function tokens(canon: string): string[] {
  return canon
    .split(/\s+/)
    .filter((t) => t.length > 0 && cplen(t) >= 3 && !STOPWORDS.has(t));
}

/** The largest candidate group, ties broken lexicographically. Mirrors `_pick`. */
function pick(candidates: Map<string, number>, keys: Iterable<string>): string {
  return [...keys].sort((a, b) => {
    const d = (candidates.get(b) ?? 0) - (candidates.get(a) ?? 0);
    if (d !== 0) return d;
    return a < b ? -1 : a > b ? 1 : 0;
  })[0];
}

const orderEvents = (events: Iterable<ChatEvent>): ChatEvent[] =>
  [...events].sort((a, b) => a.ts_ms - b.ts_ms || (a.id < b.id ? -1 : a.id > b.id ? 1 : 0));

/**
 * Group chat into audience signals. Deterministic, free, no model. Rule order is the spec:
 *   1. reaction wave  — laughter and emote-only, one counted bucket
 *   2. prefix         — single-word messages >=4 chars share their first 4 characters
 *   3. token          — what is left shares a content token
 * Then a prefix bucket is folded into the word it is the prefix of. Returns groups ranked by
 * count; messages that join nothing are singletons and are not returned.
 */
export function groupChat(events: Iterable<ChatEvent>, maxSamples = 3): Group[] {
  const msgs = orderEvents(events);
  const canon = new Map<string, string>();
  for (const e of msgs) canon.set(e.id, canonical(e.text) || EMPTY_KEY);

  const assigned = new Map<string, string>(); // event id -> group key
  const rules = new Map<string, GroupRule>(); // group key -> rule

  // 1. reaction wave
  for (const e of msgs) {
    if (isReaction(canon.get(e.id)!)) {
      assigned.set(e.id, REACTION_KEY);
      rules.set(REACTION_KEY, "reaction");
    }
  }

  // 2. prefix — single-word messages share their first 4 characters
  const prefixOf = new Map<string, string>();
  const counts = new Map<string, number>();
  for (const e of msgs) {
    if (assigned.has(e.id)) continue;
    const c = canon.get(e.id)!;
    if (c.includes(" ") || cplen(c) < MIN_PREFIX_LEN || !WORDISH.test(c)) continue;
    const p = "p:" + cpslice(c, 0, MIN_PREFIX_LEN);
    prefixOf.set(e.id, p);
    counts.set(p, (counts.get(p) ?? 0) + 1);
  }
  for (const [eid, p] of prefixOf) {
    if ((counts.get(p) ?? 0) >= MIN_PREFIX_GROUP) {
      assigned.set(eid, p);
      rules.set(p, "prefix");
    }
  }

  // 3. token — shared content token, on what is left. Candidate counts are read once, before any
  // message is placed, so placing one never changes where the next goes.
  const tokenOf = new Map<string, string[]>();
  const tcounts = new Map<string, number>();
  for (const e of msgs) {
    if (assigned.has(e.id)) continue;
    const toks = [...new Set(tokens(canon.get(e.id)!).map((t) => "t:" + t))].sort();
    if (toks.length === 0) continue;
    tokenOf.set(e.id, toks);
    for (const t of toks) tcounts.set(t, (tcounts.get(t) ?? 0) + 1);
  }
  const survivors = new Map<string, number>();
  for (const [t, n] of tcounts) if (n >= MIN_TOKEN_GROUP) survivors.set(t, n);
  for (const [eid, toks] of tokenOf) {
    const live = toks.filter((t) => survivors.has(t));
    if (live.length) {
      const key = pick(survivors, live);
      assigned.set(eid, key);
      rules.set(key, "token");
    }
  }

  const tally = (): Map<string, number> => {
    const f = new Map<string, number>();
    for (const key of assigned.values()) f.set(key, (f.get(key) ?? 0) + 1);
    return f;
  };
  let final = tally();

  // 4. fold a prefix bucket into the word it is the prefix of ("viol…" + "violet" -> "violet").
  const merged = new Map<string, string>();
  for (const pkey of [...final.keys()].filter((k) => rules.get(k) === "prefix")) {
    const body = pkey.slice(2);
    const cand = [...final.keys()].filter(
      (t) => rules.get(t) === "token" && t.slice(2).startsWith(body),
    );
    if (cand.length) merged.set(pkey, pick(final, cand));
  }
  for (const [eid, key] of [...assigned]) {
    const to = merged.get(key);
    if (to) assigned.set(eid, to);
  }
  final = tally();

  // A group can fall under its threshold once each message has gone to its single best group.
  const floor: Record<GroupRule, number> = {
    reaction: 1,
    prefix: MIN_PREFIX_GROUP,
    token: MIN_TOKEN_GROUP,
  };
  const kept = new Set<string>();
  for (const [k, n] of final) if (n >= floor[rules.get(k)!]) kept.add(k);

  const groups = new Map<string, Group>();
  for (const e of msgs) {
    const key = assigned.get(e.id);
    if (!key || !kept.has(key)) continue;
    let g = groups.get(key);
    if (!g) {
      const rule = rules.get(key)!;
      const label =
        key === REACTION_KEY
          ? REACTION_LABEL
          : rule === "prefix"
            ? `${key.slice(2)}…`
            : key.slice(2);
      g = {
        key,
        rule,
        label,
        count: 0,
        first_ts_ms: e.ts_ms,
        last_ts_ms: e.ts_ms,
        event_ids: [],
        samples: [],
      };
      groups.set(key, g);
    }
    g.count += 1;
    g.last_ts_ms = e.ts_ms;
    g.event_ids.push(e.id);
    if (g.samples.length < maxSamples && !g.samples.includes(e.text)) {
      g.samples.push(e.text); // verbatim, never the canonical form
    }
  }

  return [...groups.values()].sort(
    (a, b) =>
      b.count - a.count ||
      a.first_ts_ms - b.first_ts_ms ||
      (a.key < b.key ? -1 : a.key > b.key ? 1 : 0),
  );
}

/** `N messages -> M rows -> K singletons`, the footer line the board owes the reader. */
export function groupedSummary(events: Iterable<ChatEvent>, groups: Group[]): GroupedSummary {
  const messages = [...events].length;
  const grouped = groups.reduce((s, g) => s + g.count, 0);
  return { messages, groups: groups.length, grouped, ungrouped: messages - grouped };
}
