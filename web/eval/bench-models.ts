// Speed and a smoke test per candidate. The smoke test is NOT the selection criterion (that is the
// labelled dev split); it only catches a broken pooling/prefix or a model that cannot tell an
// audio complaint from a game request at all.
import { CANDIDATES, load, cos } from "./embedders";

const PROBE: string[][] = [
  ["this game is so boring", "bro switch games already", "play fortnite instead", "we need a different game", "why is he still playing this"],
  ["his mic is muted", "we can't hear him", "audio is broken", "someone tell him to fix sound"],
  ["what's your sens", "what sensitivity do you use", "sens?", "whats ur dpi"],
  ["звук пропал", "не слышно стримера", "микрофон выключен"],
];
const DISTRACT = ["1000 channel points", "I lost my prediction", "how many points do I need", "can someone redeem this", "LUL", "hi chat", "that was a nice shot", "what time is it there"];

const only = process.argv.slice(2);
const sample = Array.from({ length: 256 }, (_, i) => `${["lol that was insane", "what game is this", "W stream", "he's so bad at this", "chat is he cooked", "no way bro"][i % 6]} ${i}`);
for (const c of CANDIDATES.filter((c) => !only.length || only.includes(c.key))) {
  const e = await load(c);
  const groups = await Promise.all(PROBE.map((g) => e.embed(g)));
  const distract = await e.embed(DISTRACT);
  let within = 0, wn = 0, between = 0, bn = 0;
  groups.forEach((g, gi) => {
    for (let i = 0; i < g.length; i++) for (let j = i + 1; j < g.length; j++) (within += cos(g[i], g[j])), wn++;
    for (const v of g) {
      for (const d of distract) (between += cos(v, d)), bn++;
      groups.forEach((h, hi) => { if (hi !== gi) for (const w of h) (between += cos(v, w)), bn++; });
    }
  });
  // English audio vs Russian audio: does the model place the same complaint together across languages?
  const crossLang = cos(groups[1][1], groups[3][1]);
  await e.embed(sample.slice(0, 64)); // warm
  const t0 = performance.now();
  await e.embed(sample);
  const per = (performance.now() - t0) / sample.length;
  console.log(
    `${c.key.padEnd(15)} ${String(c.mb).padStart(4)}MB load ${Math.round(e.loadMs).toString().padStart(5)}ms  ` +
      `within ${(within / wn).toFixed(3)} between ${(between / bn).toFixed(3)} gap ${((within / wn) - (between / bn)).toFixed(3)}  ` +
      `en↔ru ${crossLang.toFixed(3)}  ${per.toFixed(2)} ms/msg (node, batch 64)`,
  );
}
