// Faithful port of `src/ts/workflow/reduce.py::canonical` and its helpers.
//
// The subtle part is matching Python's *Unicode* regex semantics in JavaScript:
//   - Python `str.casefold()`   -> JS `.toLowerCase()`. These agree for Latin, Cyrillic, CJK,
//     digits and emoji — everything that actually shows up in Twitch chat. They differ for a
//     few exotic code points (German ß -> "ss" under casefold but stays "ß" under toLowerCase,
//     Greek final sigma, etc.). Those do not occur in the parity corpus and do not affect chat
//     clustering; the divergence is documented rather than papered over.
//   - Python `\p{P}` punctuation, Unicode `\s`, and Unicode `\w`/`\b` all need the `u` flag and,
//     for word boundaries, explicit lookarounds because JS `\b`/`\w` are ASCII-only.

// A char repeated 3+ times collapses to two: "loool" -> "lool", "😂😂😂😂" -> "😂😂".
const CHAR_RUN = /(.)\1{2,}/gu;
// A 1-4 char unit repeated 3+ times collapses to two repeats: "hahahaha" -> "haha",
// "ахахахаха" -> "ахаха". Non-greedy so the shortest repeating unit wins.
const NGRAM_RUN = /(.{1,4}?)\1{2,}/gu;
// A whole word repeated with spaces collapses to one: "lul lul lul" -> "lul". Python uses
// `(\b\w+\b)(\s+\1\b)+`; JS `\b`/`\w` are ASCII-only, so Unicode word chars (`\p{L}\p{N}_`,
// which is what Python's Unicode `\w` matches) and boundaries are spelled out with lookarounds.
const WORD = "[\\p{L}\\p{N}_]";
const EMOTE_RUN = new RegExp(
  `(?<!${WORD})(${WORD}+)(?:\\s+\\1(?!${WORD}))+`,
  "gu",
);
const WHITESPACE = /\s+/gu;
// Unicode punctuation (General_Category = Punctuation, i.e. Python's category starting with "P",
// which includes the connector "_"). Symbols (category S*, where emoji live) are intentionally
// kept.
const PUNCT = /\p{P}/gu;

/** Remove Unicode punctuation, keep symbols. Mirrors `_strip_punctuation`. */
export function stripPunctuation(text: string): string {
  return text.replace(PUNCT, " ");
}

/**
 * Collapse a chat message to its semantic skeleton. Deterministic, no model, no randomness.
 * 'AHAHAHAHA', 'ahahaha' and 'AHAHA AHAHA' all collapse together; 'left' and 'LEFT!!!' do too.
 */
// The live board recounts the whole window every ~1.5s, and chat repeats itself constantly, so the
// same strings are canonicalised over and over. `canonical` is pure, so a bounded memo is safe.
const CACHE_MAX = 20_000;
const cache = new Map<string, string>();

export function canonical(text: string): string {
  const key = text ?? "";
  const hit = cache.get(key);
  if (hit !== undefined) return hit;
  const out = canonicalUncached(key);
  if (cache.size >= CACHE_MAX) cache.delete(cache.keys().next().value as string);
  cache.set(key, out);
  return out;
}

function canonicalUncached(text: string): string {
  let t = text.normalize("NFKC").toLowerCase();
  t = stripPunctuation(t);
  t = t.replace(WHITESPACE, " ").trim();
  t = t.replace(CHAR_RUN, "$1$1");
  t = t.replace(NGRAM_RUN, "$1$1");
  t = t.replace(EMOTE_RUN, "$1");
  return t;
}
