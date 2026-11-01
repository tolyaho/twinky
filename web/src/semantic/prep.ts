// Stage A/B of semantic grouping: decide, per message and without any model, what kind of message
// it is — and for the ones that carry meaning in words, the text that gets embedded.
//
// Reactions are recognised by vocabulary, not embedded: an emote name tokenises into noise, and
// "KEKW" sits close to every short line in embedding space, which is how the historical embedding
// experiment chained unrelated messages together (evals/grouping/README.md). Laughter is one
// meaning; hype, sadness, shock, confusion and so on are each their own, never one "reaction wave".
import { canonical } from "../cluster/canonical";

export type Kind =
  | "reaction" // emotes / laughter / emoji only: grouped by family, never embedded
  | "text" // carries meaning in words: embedded and grouped by meaning
  | "lowinfo" // a bare number, one stopword, the streamer's name: grouped only if identical
  | "command" // !xyz: grouped only if identical
  | "skip"; // links and known bots: never grouped

export type Family =
  | "laughing"
  | "hype"
  | "sad"
  | "shock"
  | "confused"
  | "love"
  | "cringe"
  | "bored"
  | "gg"
  | "loss"
  | "greeting"
  | "agree"
  | "doubt"
  | "awkward"
  | "salute";

export interface Prepared {
  kind: Kind;
  /** reaction: the family, or `emote:<name>` for an emote whose meaning is not known */
  family?: string;
  /** text: what is embedded (emotes, mentions and the streamer's name removed). lowinfo/command:
   * the identity that identical messages share. */
  key: string;
}

// Lowercased tokens per family. Small on purpose: a word missing here is just embedded instead.
const FAMILY_WORDS: Record<Family, string[]> = {
  laughing: ["lul", "lulw", "kekw", "kek", "kekl", "omegalul", "icant", "pepelaugh", "pepela", "lmao", "lmfao", "rofl", "xd", "xdd", "😂", "🤣", "💀", "ded", "dead", "kekwait", "elegiggle", "4head", "lulwut", "hah", "heh"],
  hype: ["pog", "pogchamp", "poggers", "pogu", "poggies", "pogcrazy", "letsgo", "w", "ww", "www", "hype", "🔥", "pogg", "gigachad", "ez", "nice", "oo", "ooo", "goo", "huge", "solid", "clean"],
  sad: ["sadge", "biblethump", "pepehands", "f", "rip", "sadgecry", "😢", "💔", "pain", "peeposad"],
  shock: ["monkas", "monkaw", "monkaomega", "wutface", "d:", "😱", "😳", "😨", "omg", "wtf", "nooo", "noo", "aa", "aaa", "damn", "dam", "crazy", "scared", "😨"],
  confused: ["?", "huh", "huhh", "wut", "wot", "🤔", "confused", "wat", "что"],
  love: ["<3", "❤️", "❤", "♥", "💜", "💕", "🥰", "peepolove", "ily", "love"],
  cringe: ["cringe", "😬", "🤢", "weirdchamp", "pepega", "facepalm", "🤦"],
  bored: ["residentsleeper", "😴", "zzz", "boring"],
  gg: ["gg", "ggs", "ggwp", "clap", "👏"],
  loss: ["l", "ll", "lll"],
  greeting: ["hi", "hello", "hey", "yo", "hii", "heyy", "hai", "привет", "ку", "здарова", "peepohey", "heyguys", "vohiyo", "hiii", "sup", "o/"],
  agree: ["yep", "yup", "yes", "yeah", "yea", "ya", "true", "tru", "facts", "fax", "exactly", "real", "fr", "frfr", "based", "mhm", "agreed", "agree", "indeed", "correct", "+1", "bingo", "да", "ага", "угу", "точно", "факт", "факты", "база", "реально", "согласен"],
  doubt: ["sure", "sureman", "surebro", "okbro", "clueless", "copium", "copege", "cope", "suree"],
  awkward: ["erm", "uhm", "umm", "um", "uh", "uhh", "ehm", "hm", "hmm", "эм", "хм", "ммм"],
  salute: ["o7", "07"],
};
const FAMILY_OF = new Map<string, Family>();
for (const [f, words] of Object.entries(FAMILY_WORDS) as [Family, string[]][]) for (const w of words) FAMILY_OF.set(w, f);

// Laughter as typed, after `canonical` has folded repeats ("AHAHAHAHA" -> "ahaha").
const LAUGH = /^(?:l+o+l+(?:ol)*|lmf?ao+|rofl|kekw?|xd+|(?:a?ha){2,}h?|ahah[ah]*|(?:he){2,}|(?:а?ха){2,}х?|ахах[ах]*|(?:хе){2,}|ору+|орнул)$/u;
// Third-party emotes are plain words; most follow these shapes (catJAM, peepoHey, monkaS, KEKW).
const EMOTE_SHAPE = /^(?:[a-z]+[A-Z][A-Za-z0-9]*|[A-Z][a-z]+[A-Z][A-Za-z]*|[A-Z]{2,}[a-z]+|pepe\w+|peepo\w+|monka\w*|\w*(?:Jam|JAM|Pls|PLS)\w*)$/;
// Emoji and symbols only. Digits are Unicode emoji components, so a symbol must be present: "100"
// is a number, not an emoji.
const EMOJI_ONLY = /^(?=.*[\p{Extended_Pictographic}\p{S}])[\p{Extended_Pictographic}\p{Emoji_Component}‍️\p{S}]+$/u;
// Chat bots by login, the same list the evaluation capture flagged (web/eval/capture.mjs).
const BOT_LOGIN = /^(nightbot|streamelements|moobot|fossabot|streamlabs|wizebot|botrixoficial|sery_bot|kofistreambot|pokemoncommunitygame)$/i;
export const isBotLogin = (login: string): boolean => BOT_LOGIN.test(login);

const URL = /\bhttps?:\/\/|\bwww\.\S+\.\w{2,}/i;
const MENTION = /@\w+/g;
const NUMBERISH = /^[\d.,%+\-x×]+$/;

const STOP = new Set(
  "a an and are as at be but by can do for from get got he him his i if in is it its just me my no not of on or so that the this to too u up was we what why with you yes yeah yep nah ok okay bro bruh chat lol everyone everybody all guys yall people fam friends stream streamer twitch oh ah man dude".split(" "),
);

// Whole messages that are a reaction although their words are ordinary ones.
const PHRASES = new Map<string, Family>([
  ["lets go", "hype"], ["lets goo", "hype"], ["let s go", "hype"], ["let s goo", "hype"], ["lesgo", "hype"], ["lessgo", "hype"], ["поехали", "hype"],
  ["im dead", "laughing"], ["i m dead", "laughing"], ["i cant", "laughing"], ["i can t", "laughing"], ["я не могу", "laughing"],
  ["what", "confused"], ["wait what", "confused"], ["what happened", "confused"], ["чего", "confused"], ["шо", "confused"],
  ["come on", "hype"], ["lets gooo", "hype"], ["oh damn", "shock"], ["holy shit", "shock"], ["oh my god", "shock"], ["oh crazy", "shock"],
  ["likely story", "doubt"], ["sure buddy", "doubt"], ["sure bro", "doubt"], ["ok bro", "doubt"],
]);

// Characters chat clients insert to dodge Twitch's duplicate-message filter ("yup ͏"), and other
// invisible ones: they would make identical messages look different.
const INVISIBLE = /[\u034f\u00ad\u180e\u200b-\u200f\u2060-\u2064\ufeff\u2800\u{e0000}-\u{e007f}]/gu;

// Third-party emote names are composed from known roots: PrideLaugh, peepoGiggles, monkaGIGA.
const EMOTE_ROOTS: [RegExp, Family][] = [
  [/laugh|giggle|lul|kek|icant|omegalul/i, "laughing"],
  [/^monka|scared|fear/i, "shock"],
  [/sadge|cry|hands$|bibl/i, "sad"],
  [/pog/i, "hype"],
  [/clap/i, "gg"],
  [/love|heart|hug/i, "love"],
  [/hey|wave|hello/i, "greeting"],
  [/huh|confus/i, "confused"],
  [/cringe|weird/i, "cringe"],
  [/sleep|zzz|bored/i, "bored"],
  [/^sure|clueless|cope/i, "doubt"],
];
// All-caps variants of laughter emotes: KEKWQ, LULW, OMEGALULIGUESS
const CAPS_LAUGH = /^(?:KEK|LUL|OMEGALUL|LMAO)[A-Z]*$/;

function familyOfToken(raw: string): Family | null {
  const t = raw.toLowerCase();
  const f = FAMILY_OF.get(t) ?? FAMILY_OF.get(canonical(t).replace(/ /g, ""));
  if (f) return f;
  // a long run of one letter ("NICEEEEE", "Daaamn") folded all the way
  if (/(.)\1\1/u.test(t)) {
    const g = FAMILY_OF.get(t.replace(/(.)\1+/gu, "$1"));
    if (g) return g;
  }
  if (EMOJI_ONLY.test(raw)) {
    // "😂😂😂": the family of the first emoji that has one
    for (const ch of Array.from(raw)) {
      const g = FAMILY_OF.get(ch);
      if (g) return g;
    }
    return null;
  }
  const c = canonical(t).replace(/ /g, "");
  if (LAUGH.test(c)) return "laughing";
  if (/^\?+$/.test(t)) return "confused";
  if (/^!+$/.test(t)) return "shock";
  if (CAPS_LAUGH.test(raw)) return "laughing";
  if (EMOTE_SHAPE.test(raw)) for (const [re, fam] of EMOTE_ROOTS) if (re.test(raw)) return fam;
  return null;
}

// Family members that are emote names, not words: removed from a sentence before it is embedded.
// Everything else in FAMILY_WORDS is an ordinary word ("boring", "rip", "love") and stays in the
// sentence, because "this game is so boring" means something "this game is so" does not.
const EMOTE_NAMES = new Set(
  "lul lulw kekw kek kekl omegalul icant pepelaugh pepela xd xdd pog pogchamp poggers pogu poggies pogcrazy pogg gigachad sadge biblethump pepehands sadgecry peeposad monkas monkaw monkaomega wutface d: peepolove weirdchamp pepega residentsleeper peepohey heyguys vohiyo elegiggle 4head kekwait lulwut o7 <3".split(" "),
);

function isEmote(raw: string): boolean {
  return EMOTE_NAMES.has(raw.toLowerCase()) || EMOTE_SHAPE.test(raw) || EMOJI_ONLY.test(raw);
}

// Words that address the audience rather than say something: "chat, is this real", "L chatter".
// Like the streamer's name, they are not what a message is about, and a model comparing short
// messages compares mostly them (a 15-message false merge held together by "chatter").
const VOCATIVES = new Set(["chat", "chatter", "chatters"]);

export interface PrepExtra {
  /** words Twitch itself marked as emotes in this message (the IRC `emotes` tag) */
  emotes?: ReadonlySet<string>;
  /** leave the audience-address words out of what is compared (see VOCATIVES) */
  vocatives?: boolean;
}

/**
 * Classify one message. `channel` is the streamer's login: on its own it says nothing, and inside
 * a sentence it is removed so that "jynxzi is the goat" and "jynxzi you're trash" are compared on
 * what they say, not on the name they share.
 */
export function prepare(text: string, channel: string, bot = false, extra: PrepExtra = {}): Prepared {
  const raw = (text ?? "").replace(INVISIBLE, "").trim();
  if (bot) return { kind: "skip", key: "" };
  if (URL.test(raw)) return { kind: "skip", key: "" };
  if (raw.startsWith("!")) return { kind: "command", key: raw.split(/\s+/)[0].toLowerCase() };

  const phrase = PHRASES.get(canonical(raw.replace(MENTION, " ")));
  if (phrase) return { kind: "reaction", family: phrase, key: "" };

  const name = channel.toLowerCase();
  const content: string[] = []; // the words that are embedded
  const families: string[] = [];
  let emoteName: string | null = null;
  let other = 0; // words that are neither reaction words nor stopwords
  for (const w of raw.replace(MENTION, " ").split(/\s+/).filter(Boolean)) {
    const bare = w.replace(/^[^\p{L}\p{N}<?!:]+|[^\p{L}\p{N}>?!)]+$/gu, "") || w;
    const low = bare.toLowerCase();
    if (low === name || low === `${name}s`) continue; // the streamer's name carries no meaning here
    if (extra.vocatives && VOCATIVES.has(low)) continue;
    const fam = familyOfToken(bare);
    if (isEmote(bare) || extra.emotes?.has(w) || extra.emotes?.has(bare)) {
      if (fam) families.push(fam);
      else emoteName ??= low;
      continue; // an emote name tokenises into noise: never embedded
    }
    content.push(w);
    if (fam) families.push(fam);
    else if (!STOP.has(canonical(low)) && !NUMBERISH.test(low)) other++;
  }

  const contentText = canonical(content.join(" "));
  if (other > 0) return { kind: "text", key: contentText };
  // nothing left but reaction words, stopwords and numbers
  if (families.length && !NUMBERISH.test(contentText)) return { kind: "reaction", family: dominant(families), key: "" };
  if (!contentText && emoteName) return { kind: "reaction", family: `emote:${emoteName}`, key: "" };
  // "1", "100", "ok", the streamer's name alone: only identical repeats are a signal (a vote)
  return { kind: "lowinfo", key: contentText || canonical(raw) || raw.toLowerCase() };
}

function dominant(families: string[]): string {
  const n = new Map<string, number>();
  for (const f of families) n.set(f, (n.get(f) ?? 0) + 1);
  return [...n.entries()].sort((a, b) => b[1] - a[1] || families.indexOf(a[0]) - families.indexOf(b[0]))[0][0];
}

export const FAMILY_LABEL: Record<Family, string> = {
  laughing: "Chat is laughing",
  hype: "Hype",
  sad: "Sad / sympathy",
  shock: "Shocked",
  confused: "Confused",
  love: "Love for the stream",
  cringe: "Cringing",
  bored: "Bored",
  gg: "GG / applause",
  loss: "Calling it an L",
  greeting: "Saying hi",
  agree: "Agreeing",
  doubt: "Not buying it",
  awkward: "Awkward",
  salute: "Saluting o7",
};
