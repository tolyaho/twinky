// Capture real Twitch chat for the semantic-clustering evaluation. Anonymous, read-only IRC
// (the same justinfan login the app uses). Authors are pseudonymised with a per-run salt that is
// never written anywhere, and @mentions in message text are masked, before anything touches disk.
//
//   node web/eval/capture.mjs <minutes> <outdir> chan1 chan2 ...
import { createHmac, randomBytes } from "node:crypto";
import { mkdirSync, appendFileSync } from "node:fs";
import { join } from "node:path";

const [minutes, outdir, ...channels] = process.argv.slice(2);
const SALT = randomBytes(32);
const pseudo = (login) => "u_" + createHmac("sha256", SALT).update(login.toLowerCase()).digest("hex").slice(0, 10);
const mask = (text) => text.replace(/@\w{2,25}/g, "@user");
mkdirSync(outdir, { recursive: true });
const counts = Object.fromEntries(channels.map((c) => [c, 0]));

function tags(raw) {
  const t = {};
  for (const kv of raw.split(";")) {
    const i = kv.indexOf("=");
    t[kv.slice(0, i)] = kv.slice(i + 1);
  }
  return t;
}

const ws = new WebSocket("wss://irc-ws.chat.twitch.tv:443");
ws.onopen = () => {
  ws.send("CAP REQ :twitch.tv/tags twitch.tv/commands");
  ws.send("PASS SCHMOOPIIE");
  ws.send(`NICK justinfan${Math.floor(10000 + Math.random() * 80000)}`);
  for (const c of channels) ws.send(`JOIN #${c}`);
};
ws.onmessage = (ev) => {
  for (const line of String(ev.data).split("\r\n")) {
    if (!line) continue;
    if (line.startsWith("PING")) { ws.send("PONG :tmi.twitch.tv"); continue; }
    const m = /^@(\S+) :(\w+)!\S+ PRIVMSG #(\w+) :(.*)$/.exec(line);
    if (!m) continue;
    const t = tags(m[1]);
    const login = m[2];
    const ch = m[3];
    const row = {
      id: t.id,
      ts_ms: Number(t["tmi-sent-ts"]) || Date.now(),
      author: pseudo(login),
      // known chat bots are kept but flagged, so the evaluation can test that they are excluded
      bot: /^(nightbot|streamelements|moobot|fossabot|streamlabs|wizebot|botrixoficial|sery_bot|kofistreambot|pokemoncommunitygame)$/i.test(login),
      text: mask(m[4]),
    };
    appendFileSync(join(outdir, `${ch}.jsonl`), JSON.stringify(row) + "\n");
    counts[ch]++;
  }
};
const stop = () => {
  console.log(JSON.stringify(counts));
  process.exit(0);
};
setTimeout(stop, Number(minutes) * 60_000);
setInterval(() => console.log(new Date().toISOString(), JSON.stringify(counts)), 60_000);
