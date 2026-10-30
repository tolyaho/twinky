"""Current-gate projection of immutable recorded cards; no model calls or disk writes."""
import hashlib
import json
from pathlib import Path
from ..provenance import CURRENT_GATE, apply_gate

def load_result(path, index):
    raw = Path(path).read_bytes()
    doc = json.loads(raw)
    for window in doc.get("windows", []):
        cards = sorted(window.get("verified", []) + window.get("rejected", []),
                       key=lambda c: str(c.get("signal_id", "")))
        clean = [{k: v for k, v in c.items() if k not in ("gate", "status", "action")}
                 for c in cards]
        window.update(apply_gate(clean, index))
        for card in window["verified"]:
            if card.get("type") == "audience_answer" and card.get("distribution"):
                card["action"] = {"kind": "draft_poll", "state": "pending_approval"}
    doc["projection"] = {"gate_version": CURRENT_GATE,
                         "source_sha256": hashlib.sha256(raw).hexdigest(),
                         "meaning": "citation and time checks; causal hypotheses are unverified"}
    if "counts" in doc:
        doc["counts"].update(verified=sum(len(w["verified"]) for w in doc["windows"]),
                              rejected=sum(len(w["rejected"]) for w in doc["windows"]))
    return doc
