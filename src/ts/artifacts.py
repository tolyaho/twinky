"""Protect frozen evidence. Changed reruns belong in an explicit derived directory."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def write_text(path: Path, body: str) -> None:
    path = Path(path)
    if path.exists():
        if path.read_bytes() == body.encode("utf-8"):
            return
        if any(base in path.resolve().parents for base in
               (ROOT / "evidence", ROOT / "trajectories")):
            raise ValueError(f"refusing to replace frozen artifact {path}; use --out .runtime/<run>")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
