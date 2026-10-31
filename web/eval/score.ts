// Scoring a grouping against labels. Pairwise precision/recall/F1 use the convention of
// evals/grouping (x never pairs, unsure is excluded both ways) so old and new numbers compare.
// Pairwise numbers are dominated by big groups (one 50-message laughter group is 1,225 pairs), so
// message-level B-cubed scores and cluster-level counts sit beside them: how many shown groups
// are false merges, how fragmented real groups are, and whether noise stays ungrouped.

export type Gold = Map<string, string>; // id -> cluster | "x" | "unsure"
export type Pred = Map<string, string | null>; // id -> predicted group, null = ungrouped

export interface Score {
  pairs: { tp: number; pred: number; gold: number; p: number; r: number; f1: number };
  bcubed: { p: number; r: number; f1: number };
  shown: number; // predicted groups
  falseMerges: number; // predicted groups whose largest gold share is under 2/3
  falseMergeShare: number;
  goldGroups: number;
  fragmentation: number; // predicted groups per covered gold group (1 = whole)
  goldCovered: number; // share of gold-grouped messages that are grouped at all
  noiseKept: number; // share of gold `x` messages left ungrouped
}

const f1 = (p: number, r: number) => (p + r ? (2 * p * r) / (p + r) : 0);

export function score(gold: Gold, pred: Pred): Score {
  const ids = [...gold.keys()].filter((id) => gold.get(id) !== "unsure");
  const g = (id: string) => {
    const v = gold.get(id)!;
    return v === "x" ? null : v;
  };
  const p = (id: string) => pred.get(id) ?? null;

  let tp = 0, predPairs = 0, goldPairs = 0;
  for (let i = 0; i < ids.length; i++) {
    for (let j = i + 1; j < ids.length; j++) {
      const gi = g(ids[i]), gj = g(ids[j]), pi = p(ids[i]), pj = p(ids[j]);
      const gp = gi !== null && gi === gj;
      const pp = pi !== null && pi === pj;
      if (gp) goldPairs++;
      if (pp) predPairs++;
      if (gp && pp) tp++;
    }
  }
  const pp = predPairs ? tp / predPairs : 0;
  const pr = goldPairs ? tp / goldPairs : 0;

  // B-cubed, with ungrouped / x messages as singletons of their own
  const predOf = (id: string) => p(id) ?? `_solo_${id}`;
  const goldOf = (id: string) => g(id) ?? `_solo_${id}`;
  const byPred = new Map<string, string[]>();
  const byGold = new Map<string, string[]>();
  for (const id of ids) {
    (byPred.get(predOf(id)) ?? byPred.set(predOf(id), []).get(predOf(id))!).push(id);
    (byGold.get(goldOf(id)) ?? byGold.set(goldOf(id), []).get(goldOf(id))!).push(id);
  }
  let bp = 0, br = 0;
  for (const id of ids) {
    const pc = byPred.get(predOf(id))!;
    const gc = byGold.get(goldOf(id))!;
    const both = pc.filter((o) => goldOf(o) === goldOf(id)).length;
    bp += both / pc.length;
    br += both / gc.length;
  }
  bp /= ids.length || 1;
  br /= ids.length || 1;

  // cluster level
  const shownGroups = [...byPred.entries()].filter(([k]) => !k.startsWith("_solo_"));
  let falseMerges = 0;
  for (const [, members] of shownGroups) {
    const counts = new Map<string, number>();
    for (const m of members) counts.set(goldOf(m), (counts.get(goldOf(m)) ?? 0) + 1);
    if (Math.max(...counts.values()) / members.length < 2 / 3) falseMerges++;
  }
  const goldGroups = [...byGold.entries()].filter(([k]) => !k.startsWith("_solo_"));
  let frag = 0, fragN = 0, inGold = 0, inGoldGrouped = 0;
  for (const [, members] of goldGroups) {
    const preds = new Set(members.map((m) => p(m)).filter((x) => x !== null));
    if (preds.size) (frag += preds.size), fragN++;
    inGold += members.length;
    inGoldGrouped += members.filter((m) => p(m) !== null).length;
  }
  const noise = ids.filter((id) => g(id) === null);
  return {
    pairs: { tp, pred: predPairs, gold: goldPairs, p: pp, r: pr, f1: f1(pp, pr) },
    bcubed: { p: bp, r: br, f1: f1(bp, br) },
    shown: shownGroups.length,
    falseMerges,
    falseMergeShare: shownGroups.length ? falseMerges / shownGroups.length : 0,
    goldGroups: goldGroups.length,
    fragmentation: fragN ? frag / fragN : 0,
    goldCovered: inGold ? inGoldGrouped / inGold : 0,
    noiseKept: noise.length ? noise.filter((id) => p(id) === null).length / noise.length : 1,
  };
}

/** Sum several windows' scores: pairs pooled, message-level scores weighted by messages. */
export function pool(scores: { s: Score; n: number }[]): Score {
  const tp = scores.reduce((a, x) => a + x.s.pairs.tp, 0);
  const pred = scores.reduce((a, x) => a + x.s.pairs.pred, 0);
  const gold = scores.reduce((a, x) => a + x.s.pairs.gold, 0);
  const n = scores.reduce((a, x) => a + x.n, 0) || 1;
  const w = (f: (s: Score) => number) => scores.reduce((a, x) => a + f(x.s) * x.n, 0) / n;
  const shown = scores.reduce((a, x) => a + x.s.shown, 0);
  const falseMerges = scores.reduce((a, x) => a + x.s.falseMerges, 0);
  const p = pred ? tp / pred : 0;
  const r = gold ? tp / gold : 0;
  const bp = w((s) => s.bcubed.p), br = w((s) => s.bcubed.r);
  return {
    pairs: { tp, pred, gold, p, r, f1: f1(p, r) },
    bcubed: { p: bp, r: br, f1: f1(bp, br) },
    shown,
    falseMerges,
    falseMergeShare: shown ? falseMerges / shown : 0,
    goldGroups: scores.reduce((a, x) => a + x.s.goldGroups, 0),
    fragmentation: w((s) => s.fragmentation),
    goldCovered: w((s) => s.goldCovered),
    noiseKept: w((s) => s.noiseKept),
  };
}
