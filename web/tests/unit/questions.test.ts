import { describe, expect, it } from "vitest";
import { questions } from "../../src/cluster/pulse";
import { mergeQuestions } from "../../src/ui/Pulse";
import type { ChatEvent } from "../../src/cluster/types";

const ev = (id: string, text: string, ts: number): ChatEvent => ({ id, ts_ms: ts, author: `a${id}`, text });

describe("mergeQuestions (display)", () => {
  it("shows an identical question once, with both askers counted", () => {
    const rows = questions([
      ev("1", "WHO DO YOU THINK WINS THE FINAL?", 1),
      ev("2", "who do you think wins the final", 2),
      ev("3", "what game is this?", 3),
    ]);
    // the ported rule leaves the two identical questions apart (a shared word needs three)
    expect(rows.filter((r) => r.count === 1)).toHaveLength(3);
    const merged = mergeQuestions(rows);
    expect(merged).toHaveLength(2);
    expect(merged[0]).toMatchObject({ text: "WHO DO YOU THINK WINS THE FINAL?", count: 2 });
    expect(merged[0].event_ids).toEqual(["1", "2"]);
    expect(merged[1]).toMatchObject({ text: "what game is this?", count: 1 });
  });

  it("never loses or invents a count", () => {
    const rows = questions(
      Array.from({ length: 9 }, (_, i) => ev(String(i), i % 3 ? "is this live?" : "why is he crying?", i)),
    );
    const total = (r: { count: number }[]) => r.reduce((s, q) => s + q.count, 0);
    expect(total(mergeQuestions(rows))).toBe(total(rows));
  });
});
