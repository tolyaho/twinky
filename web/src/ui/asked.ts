// "Questions in chat": what several chatters are asking, one row per question however it was
// worded. No second grouping engine: when the board groups by meaning, a question is one of its
// groups (the model already put the paraphrases together, and the group keeps its stable id);
// on the word-rules board, only the same wording counts as the same question, because a shared
// word is not a shared question.
//
// Chat alone cannot say whether the streamer answered, or whether a question was even meant for
// them, so nothing here claims either. People are counted apart from messages: one chatter asking
// twenty times is one person asking.
import { canonical } from "../cluster/canonical";
import { isQuestion } from "../cluster/pulse";
import type { ChatEvent } from "../cluster/types";

export interface AskedQuestion {
  /** stable across recounts: the board group's key, or the wording's for the word-rules board */
  key: string;
  /** a real message, as typed (leading @mentions dropped) */
  label: string;
  /** distinct chatters who asked it */
  askers: number;
  /** the asking messages, oldest first */
  event_ids: string[];
  first_ts_ms: number;
  last_ts_ms: number;
  /** the board group that holds these messages, to open it there */
  groupKey: string | null;
  /** "meaning": the topic model put different wordings together; "wording": identical text */
  how: "meaning" | "wording";
}

export interface QuestionsView {
  repeated: AskedQuestion[];
  /** questions only one chatter asked (each once, however often they repeated it), newest first */
  others: { id: string; text: string; author: string; ts_ms: number; times: number }[];
}

// Exclamations shaped like questions: "what a play", "how lucky is that". Not something chat wants
// to know, so not shown as a question. Kept short on purpose: anything else that opens with a
// question word or ends with "?" counts.
const EXCLAIM = /^(?:what an? |what the |how (?:lucky|good|bad|crazy|insane|cute|cool|funny|sick|nice|clean|fast)\b|who cares\b)/;

const MENTION_LEAD = /^(?:@\w+[\s,:]*)+/;
const tidy = (t: string) => t.replace(MENTION_LEAD, "").replace(/\s+/g, " ").trim() || t.trim();

/**
 * Asks something: the ported question rule, minus exclamations, and at least two words — a lone
 * "why?" or "really?" says too little to know what is being asked, or to group by meaning.
 */
export function asksQuestion(text: string): boolean {
  if (!isQuestion(text)) return false;
  const c = canonical(tidy(text));
  if (c.split(" ").filter(Boolean).length < 2) return false;
  if (!EXCLAIM.test(c)) return true;
  // "what a play?" still asks; "who cares?" never does
  return /\?\s*$/.test(text.trim()) && !c.startsWith("who cares");
}

interface BoardGroup {
  key: string;
  rule: string;
  display: string;
  event_ids: readonly string[];
}

export function questionsInChat(
  groups: readonly BoardGroup[],
  events: ReadonlyMap<string, ChatEvent>,
  byMeaning: boolean,
): QuestionsView {
  const asked: ChatEvent[] = [];
  for (const e of events.values()) if (!e.bot && asksQuestion(e.text)) asked.push(e);
  const askedIds = new Set(asked.map((e) => e.id));
  const groupOf = new Map<string, BoardGroup>();
  for (const g of groups) for (const id of g.event_ids) groupOf.set(id, g);

  const repeated: AskedQuestion[] = [];
  const placed = new Set<string>();
  const add = (key: string, label: string, ids: string[], groupKey: string | null, how: AskedQuestion["how"]) => {
    const evs = ids.map((id) => events.get(id)!).sort((a, b) => a.ts_ms - b.ts_ms || (a.id < b.id ? -1 : 1));
    const askers = new Set(evs.map((e) => e.author)).size;
    if (askers < 2) return; // one person repeating a question is not the room asking it
    repeated.push({
      key,
      label,
      askers,
      event_ids: evs.map((e) => e.id),
      first_ts_ms: evs[0].ts_ms,
      last_ts_ms: evs[evs.length - 1].ts_ms,
      groupKey,
      how,
    });
    for (const id of ids) placed.add(id);
  };

  // the same words, whatever the case, punctuation or @mention in front
  const byWording = (ids: readonly string[]) => {
    const byText = new Map<string, string[]>();
    for (const id of ids) {
      const k = canonical(tidy(events.get(id)!.text));
      (byText.get(k) ?? byText.set(k, []).get(k)!).push(id);
    }
    for (const [k, same] of byText) {
      // the board group holding most of them, if any, so the row can open it
      const n = new Map<string, number>();
      for (const id of same) {
        const g = groupOf.get(id);
        if (g) n.set(g.key, (n.get(g.key) ?? 0) + 1);
      }
      const best = [...n].sort((a, b) => b[1] - a[1])[0];
      const home = best && best[1] * 2 >= same.length ? best[0] : null;
      add(`w:${k}`, commonest(same.map((id) => tidy(events.get(id)!.text))), same, home, "wording");
    }
  };

  if (byMeaning) {
    // a question group — most of its messages ask, in whatever words: the model's grouping is
    // the question
    for (const g of groups) {
      if (g.rule !== "question") continue;
      const ids = g.event_ids.filter((id) => askedIds.has(id));
      if (ids.length) add(`q:${g.key}`, g.display, ids, g.key, "meaning");
    }
  }
  // Everything else asked: only the same wording is the same question. Two different questions
  // inside one topic are not one question, and on the word-rules board neither is a shared word.
  byWording(asked.filter((e) => !placed.has(e.id)).map((e) => e.id));
  // more people first; then the one asked most recently
  repeated.sort((a, b) => b.askers - a.askers || b.last_ts_ms - a.last_ts_ms || (a.key < b.key ? -1 : 1));

  // everything else that was asked, once per chatter and wording
  const seen = new Map<string, QuestionsView["others"][number]>();
  for (const e of asked) {
    if (placed.has(e.id)) continue;
    const k = `${e.author}\u0000${canonical(tidy(e.text))}`;
    const had = seen.get(k);
    if (had) {
      had.times++;
      if (e.ts_ms > had.ts_ms) Object.assign(had, { id: e.id, text: e.text, ts_ms: e.ts_ms });
    } else seen.set(k, { id: e.id, text: e.text, author: e.author, ts_ms: e.ts_ms, times: 1 });
  }
  const others = [...seen.values()].sort((a, b) => b.ts_ms - a.ts_ms);
  return { repeated, others };
}

function commonest(xs: string[]): string {
  const n = new Map<string, number>();
  for (const x of xs) n.set(x, (n.get(x) ?? 0) + 1);
  let best = xs[0] ?? "", bn = 0;
  for (const [x, k] of n) if (k > bn || (k === bn && x < best)) (best = x), (bn = k);
  return best;
}
