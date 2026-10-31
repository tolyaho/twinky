// Chat-only port of the measured parts of `src/ts/report/board.py`: `is_question`, `questions`,
// and the right-rail statistics (`rail`, minus the speech/frames/gate fields a chat-only Tier 0
// cannot produce). Everything here is arithmetic over the window — no model, no fabrication.
import { canonical } from "./canonical";
import { groupChat, groupedSummary, STOPWORDS } from "./group";
import type { ChatEvent, Counted } from "./types";

const RATE_BUCKET_MS = 10_000; // the sparkline's resolution, and the unit "peak burst" is in
const TOP_SHARE = 0.1; // "concentration" is the share of messages from the top 10%

const WH_WORDS = new Set(
  "who whos what whats when whens where wheres why whys how hows which".split(" "),
);
const AUX_WORDS = new Set(
  "is are do does did can could would should will has have was were any anyone".split(" "),
);

export interface QuestionRow {
  text: string;
  count: number;
  event_ids: string[];
  variants: string[];
  ts_ms: number;
}

export interface Pulse {
  messages: number;
  rate: number[];
  peak_burst: number;
  peak_per_second: number;
  unique_chatters: number;
  new_chatters: number;
  messages_per_chatter: number;
  concentration: number;
  reaction_wave: number;
  active_groups: number;
  composition: { messages: number; groups: number; singletons: number };
  questions: QuestionRow[];
}

// Python `round()` is round-half-to-even; JS `Math.round` is half-up. These denominators rarely
// land exactly on a half, but match Python so parity vectors do not drift.
function pyRound(x: number, nd: number): number {
  const m = 10 ** nd;
  const y = x * m;
  const f = Math.floor(y);
  const diff = y - f;
  let r: number;
  if (diff > 0.5) r = f + 1;
  else if (diff < 0.5) r = f;
  else r = f % 2 === 0 ? f : f + 1;
  return r / m;
}

function contentTokens(text: string): string[] {
  return canonical(text)
    .split(/\s+/)
    .filter((t) => t.length > 0 && Array.from(t).length >= 3 && !STOPWORDS.has(t));
}

/** Ends with a question mark, or opens with a question word — and says something either way. */
export function isQuestion(text: string): boolean {
  const stripped = (text ?? "").trim();
  if (!stripped) return false;
  const opening = canonical(stripped).split(/\s+/).filter(Boolean).slice(0, 2);
  const asks =
    stripped.endsWith("?") ||
    opening.some((w) => WH_WORDS.has(w)) ||
    (opening.length > 0 && AUX_WORDS.has(opening[0]));
  return asks && contentTokens(stripped).length > 0;
}

/** The window's questions, grouped so twenty phrasings count once, ranked by how many asked. */
export function questions(events: Iterable<ChatEvent>): QuestionRow[] {
  const asked = [...events].filter((e) => isQuestion(e.text));
  if (asked.length === 0) return [];
  const groups = groupChat(asked);
  const placed = new Set<string>();
  for (const g of groups) for (const id of g.event_ids) placed.add(id);

  const out: QuestionRow[] = groups.map((g) => ({
    text: g.samples[0],
    count: g.count,
    event_ids: g.event_ids,
    variants: g.samples,
    ts_ms: g.first_ts_ms,
  }));
  for (const e of asked) {
    if (!placed.has(e.id)) {
      out.push({ text: e.text, count: 1, event_ids: [e.id], variants: [e.text], ts_ms: e.ts_ms });
    }
  }
  out.sort(
    (a, b) =>
      b.count - a.count ||
      a.ts_ms - b.ts_ms ||
      (a.text < b.text ? -1 : a.text > b.text ? 1 : 0),
  );
  return out;
}

function buckets(chat: ChatEvent[], start: number, end: number): number[] {
  const n = Math.max(1, Math.ceil((end - start) / RATE_BUCKET_MS));
  const out = new Array<number>(n).fill(0);
  for (const e of chat) {
    const i = Math.min(n - 1, Math.max(0, Math.floor((e.ts_ms - start) / RATE_BUCKET_MS)));
    out[i] += 1;
  }
  return out;
}

/**
 * The right rail over a window — measured, never invented. `seenAuthors` is who had already
 * spoken before this window, so "new chatters" means new.
 */
export function pulse(
  events: Iterable<ChatEvent>,
  start: number,
  end: number,
  seenAuthors?: Iterable<string>,
  precomputed?: readonly Counted[], // the engine already grouped this exact window; don't do it twice
): Pulse {
  const chat = [...events];
  const groups = precomputed ?? groupChat(chat);
  const summary = groupedSummary(chat, groups);

  const authors = new Map<string, number>();
  for (const e of chat) authors.set(e.author, (authors.get(e.author) ?? 0) + 1);
  const before = new Set(seenAuthors ?? []);
  const authorCounts = [...authors.values()].sort((a, b) => b - a);
  const topN = authorCounts.length ? Math.max(1, Math.trunc(authorCounts.length * TOP_SHARE)) : 0;
  const concentration = chat.length
    ? authorCounts.slice(0, topN).reduce((s, n) => s + n, 0) / chat.length
    : 0;

  const rate = buckets(chat, start, end);
  const peak = rate.length ? Math.max(...rate) : 0;
  // one reaction group under the ported rules; one per kind of reaction when grouping by meaning
  const reaction = groups.filter((g) => g.rule === "reaction").reduce((s, g) => s + g.count, 0);

  return {
    messages: chat.length,
    rate,
    peak_burst: peak,
    peak_per_second: pyRound(peak / (RATE_BUCKET_MS / 1000), 2),
    unique_chatters: authors.size,
    new_chatters: [...authors.keys()].filter((a) => !before.has(a)).length,
    messages_per_chatter: authors.size ? pyRound(chat.length / authors.size, 2) : 0,
    concentration: pyRound(concentration, 3),
    reaction_wave: reaction,
    active_groups: groups.length,
    composition: {
      messages: summary.messages,
      groups: summary.groups,
      singletons: summary.ungrouped,
    },
    questions: questions(chat),
  };
}
