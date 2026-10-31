// The plain-text view a labeller reads: one line per message, numbered, with its (pseudonymous)
// author. Labels are keyed by that number, which is far less error-prone than copying ids.
//
//   npx tsx web/eval/label-view.ts <window.json> > <window>.txt
import { readFileSync } from "node:fs";

const w = JSON.parse(readFileSync(process.argv[2], "utf8"));
const t0 = w.messages[0]?.ts_ms ?? 0;
console.log(`# window ${w.window} — channel ${w.channel}, ${w.messages.length} messages, ${w.kind}`);
console.log("# n | seconds into window | author | text   (BOT = known bot account)");
w.messages.forEach((m: { ts_ms: number; author: string; bot: boolean; text: string }, n: number) => {
  const s = ((m.ts_ms - t0) / 1000).toFixed(1).padStart(5);
  console.log(`${n} | ${s} | ${m.author}${m.bot ? " BOT" : ""} | ${m.text.replace(/\s+/g, " ")}`);
});
