#!/usr/bin/env python3
"""Generate golden parity vectors from the UNTOUCHED Python clustering.

Runs `src/ts/workflow/reduce.py` and `src/ts/report/board.py` (both stdlib-only) over a
Twitch-realistic corpus plus a slice of a real committed fixture, and writes the exact outputs to
`web/tests/fixtures/parity.json`. The Vitest suite then asserts the TypeScript port reproduces
them byte for byte. This is the evidence that the browser clustering is the same algorithm the
evaluation stands on — not a lookalike.

Run:  cd web && python3 scripts/gen_parity.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]                      # web/scripts/gen_parity.py -> repo root
sys.path.insert(0, str(REPO / "src"))

from ts.events import Event, EventIndex, order    # noqa: E402
from ts.ingest.capture import parse_privmsg        # noqa: E402
from ts.report.board import questions as py_questions, rail as py_rail  # noqa: E402
from ts.workflow.reduce import (                  # noqa: E402
    canonical,
    group_chat,
    grouped_summary,
)

OUT = HERE.parents[1] / "tests" / "fixtures" / "parity.json"

# --- canonical() corpus: everything that actually shows up in a Twitch chat --------------------
CANON_INPUTS = [
    "", "   ", "!!!", "???", ".", "...",
    "LOL", "lol", "LOOOOL", "LMAO", "LMFAO", "lmfaooooo", "ROFL", "KEKW", "xD", "xDDDD",
    "HAHAHA", "ahahaha", "AHAHA AHAHA", "hehehe", "hahahahaha",
    "ахахаха", "ахахахаха", "ХАХАХА", "хехехе", "ахах",
    "W", "L", "W STREAM", "w stream", "W STREAM!!!", "WWWWW",
    "LEFT", "LEFT!!!", "left", "  left  ",
    "😂", "😂😂😂", "😂😂😂😂😂", "LUL LUL LUL", "Pog Pog Pog Pog",
    "what game is this?", "whats the game", "WHAT HAPPENED??",
    "parabola", "parachute", "PARAGON", "VIOLET", "violet my goat", "is that violet",
    "!drops", "!uptime", "https://twitch.tv/xqc check this",
    "gg", "ggs", "yy", "no way", "NO WAY", "nooo way",
    "первый", "кек", "кек кек кек", "соси",
    "ом­но­м", "ＨＥＬＬＯ", "ﬁre", "naïve", "café",
    "same", "SAME", "sameee", "this this this this",
    "10", "10/10", "100000", "7777777",
    "D:", "<3", ":)", ">_<", "o7",
]


# --- parse_privmsg() corpus: real IRC line shapes and the ways they go wrong ------------------
TAGS = ("@badge-info=;badges=moderator/1;color=#1E90FF;display-name=SomeUser;emotes=;"
        "first-msg=0;flags=;id=abc-123-def;mod=1;returning-chatter=0;room-id=71092938;"
        "subscriber=0;tmi-sent-ts=1700000000123;turbo=0;user-id=44322889;user-type=mod")
PARSE_LINES = [
    # well-formed, with a message that itself contains colons
    f"{TAGS} :someuser!someuser@someuser.tmi.twitch.tv PRIVMSG #xqc :Hello chat! :) https://x.com",
    # empty display-name -> login ""
    (f"@id=xyz;tmi-sent-ts=1700000000456;display-name=;user-type= "
     ":u!u@u.tmi.twitch.tv PRIVMSG #xqc :no name here"),
    # empty message body after the delimiter
    (f"@id=empty1;tmi-sent-ts=1700000000999;display-name=Quiet;user-type= "
     ":q!q@q.tmi.twitch.tv PRIVMSG #xqc :"),
    # reply-parent + emotes tags present
    ("@display-name=Replier;emotes=25:0-4;id=rep-1;reply-parent-msg-id=parent-99;"
     "tmi-sent-ts=1700000001000;user-type= :r!r@r.tmi.twitch.tv PRIVMSG #xqc :Kappa back"),
    # CRLF trailing on the message
    ("@id=crlf1;tmi-sent-ts=1700000001500;display-name=Trail;user-type= "
     ":t!t@t.tmi.twitch.tv PRIVMSG #xqc :trailing text\r\n"),
    # missing id tag -> dropped
    "@tmi-sent-ts=1700000002000;display-name=NoId :n!n@n PRIVMSG #xqc :dropped",
    # missing tmi-sent-ts -> dropped
    "@id=noTs;display-name=NoTs :n!n@n PRIVMSG #xqc :dropped",
    # does not start with @ -> dropped
    ":tmi.twitch.tv 001 justinfan123 :Welcome, GLHF!",
    # PING keepalive -> not a PRIVMSG
    "PING :tmi.twitch.tv",
    # end-of-names 366 -> not a PRIVMSG
    ":justinfan1!justinfan1@justinfan1.tmi.twitch.tv 366 justinfan1 #xqc :End of /NAMES list",
    # NOTICE (e.g. msg_channel_suspended) -> not a PRIVMSG
    "@msg-id=msg_banned :tmi.twitch.tv NOTICE #xqc :You are permanently banned.",
    # malformed tag with no "=" -> dropped (Python's split("=",1) raises, caught -> None)
    "@idnoequals;tmi-sent-ts=1 :x!x@x PRIVMSG #xqc :bad tags",
    # no trailing ":" delimiter in the body -> dropped
    "@id=nocolon;tmi-sent-ts=1700000003000;display-name=X;user-type= PRIVMSG-ish line",
    # unicode + emoji message
    ("@id=uni1;tmi-sent-ts=1700000004000;display-name=Кек;user-type= "
     ":k!k@k.tmi.twitch.tv PRIVMSG #xqc :ахахаха 😂😂😂"),
]


def ev(i: int, ts: int, author: str, text: str) -> Event:
    return Event(f"m{i:04d}", "chat_message", ts, {"text": text, "author": author})


def seq(texts, *, authors=None, step=250, t0=1_700_000_000_000):
    """Build a message list from texts; authors cycle if not given one-per-message."""
    out = []
    for i, text in enumerate(texts):
        a = authors[i] if authors else f"u{i % 7:02d}"
        out.append(ev(i, t0 + i * step, a, text))
    return out


def reaction_wave():
    texts = (["LOL"] * 12 + ["LMAO"] * 8 + ["ахахаха"] * 6 + ["😂😂😂😂"] * 7
             + ["KEKW"] * 5 + ["actually that was insane"] * 1)
    return seq(texts, authors=[f"u{i:02d}" for i in range(len(texts))])


def prefix_and_fold():
    # The documented fold case: single-word VIOLET lands in `viol…`, the sentences in `violet`,
    # and the prefix bucket folds into the word. Plus an unrelated prefix family.
    texts = (["VIOLET"] * 8 + ["is that violet", "VIOLET my goat", "violet is cracked"]
             + ["parabola", "parachute", "paragon", "parasite"]  # share prefix 'para'
             + ["random singleton here", "another lonely line"])
    return seq(texts, authors=[f"u{i:02d}" for i in range(len(texts))])


def token_groups():
    texts = [
        "the game looks hard", "this game is broken", "what game is that",
        "he dropped the game", "insane clutch bro", "that clutch was insane",
        "clutch of the year", "nice clutch man", "random one off message",
        "totally unrelated thing",
    ]
    return seq(texts, authors=[f"u{i:02d}" for i in range(len(texts))])


def questions_case():
    texts = [
        "what game is this?", "whats the game", "what game is this",
        "why is he here?", "why is he here", "WHY IS HE HERE???",
        "how old is he", "???", "is this ranked?", "anyone know the song",
        "just a statement here", "no question at all",
    ]
    return seq(texts, authors=[f"u{i:02d}" for i in range(len(texts))])


def mixed_quiet():
    # Sparse chat where almost nothing should group — the honest "no signal yet" case.
    texts = ["hi", "hello there", "first time here", "cool stream", "nice"]
    return seq(texts, authors=[f"u{i:02d}" for i in range(len(texts))])


def load_fixture_slice(n=500):
    """A slice of a real committed fixture — parity on real data, not just crafted cases."""
    candidates = [
        REPO / "evals/fixtures/stableronaldo_2026-08-30T0723/chat.jsonl",
        REPO / "evals/fixtures/stableronaldo_2026-08-30T0723/raw/chat.jsonl",
    ]
    path = next((p for p in candidates if p.exists()), None)
    if path is None:
        return None, None
    rows = []
    with path.open(encoding="utf-8") as fh:
        for i, line in enumerate(fh):
            if i >= n:
                break
            r = json.loads(line)
            rows.append(ev(i, int(r["ts_ms"]), r["author"], r["text"]))
    return path.name, rows


def group_payload(name, events):
    # The product always groups events in `(ts_ms, type, event_id)` order — every call site feeds
    # group_chat from `EventIndex.window`, which sorts. Real captures have small timestamp
    # inversions vs file order, so sort here to reflect the real pipeline (and the TS port, which
    # sorts internally for the same reason).
    events = order(events)
    groups = group_chat(events)
    summary = grouped_summary(events, groups)
    index = EventIndex(events)
    start = events[0].ts_ms
    end = events[-1].ts_ms + 1
    r = py_rail(index, start, end)
    # Only the chat-only fields the TS `pulse` reproduces.
    pulse = {
        "messages": r["messages"],
        "rate": r["rate"],
        "peak_burst": r["peak_burst"],
        "peak_per_second": r["peak_per_second"],
        "unique_chatters": r["unique_chatters"],
        "new_chatters": r["new_chatters"],
        "messages_per_chatter": r["messages_per_chatter"],
        "concentration": r["concentration"],
        "reaction_wave": r["reaction_wave"],
        "active_groups": len(groups),
        "composition": {
            "messages": r["composition"]["messages"],
            "groups": r["composition"]["groups"],
            "singletons": r["composition"]["singletons"],
        },
        "questions": r["questions"],
    }
    return {
        "name": name,
        "window": [start, end],
        "events": [{"id": e.event_id, "ts_ms": e.ts_ms, "author": e.author, "text": e.text}
                   for e in events],
        "groups": [g.to_dict() for g in groups],
        "summary": summary,
        "pulse": pulse,
        "questions_fn": py_questions(events),
    }


def main() -> None:
    cases = [
        group_payload("reaction_wave", reaction_wave()),
        group_payload("prefix_and_fold", prefix_and_fold()),
        group_payload("token_groups", token_groups()),
        group_payload("questions_case", questions_case()),
        group_payload("mixed_quiet", mixed_quiet()),
    ]
    fname, rows = load_fixture_slice()
    if rows:
        cases.append(group_payload(f"real:{fname}", rows))

    data = {
        "canonical": [{"in": s, "out": canonical(s)} for s in CANON_INPUTS],
        "parse": [{"in": line, "out": parse_privmsg(line)} for line in PARSE_LINES],
        "groupCases": cases,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT} — {len(data['canonical'])} canonical, {len(cases)} group cases, "
          f"real slice: {'yes' if rows else 'no'}")


if __name__ == "__main__":
    main()
