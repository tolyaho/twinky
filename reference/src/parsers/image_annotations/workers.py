import asyncio
import base64
import json
import logging
import random
import re
import typing as tp

import aiohttp

from models import db
from models.image_annotations import ImageAnnotation, frame_job

logger = logging.getLogger("image_annotations_workers")
_COUNTER_RE = re.compile(r"^\d+/\d+\.?$")


def _extract_content(resp: dict) -> str:
    try:
        c = resp["choices"][0]["message"]["content"]
        if isinstance(c, str):
            return c
        return json.dumps(c, ensure_ascii=False)
    except Exception:
        return json.dumps(resp, ensure_ascii=False)


def _clean(s: str, lim: int = 500) -> str:
    s = (s or "").strip()
    s = " ".join(s.split())
    for pref in (
        "the image shows",
        "this image shows",
        "the frame shows",
        "this frame shows",
        "the screenshot shows",
        "this screenshot shows",
    ):
        if s.lower().startswith(pref):
            s = s[len(pref):].lstrip(" :,-.")
            break
    if len(s) > lim:
        s = s[:lim].rsplit(" ", 1)[0].rstrip(" ,;:-") + "…"
    return s


def _looks_like_counter(s: str) -> bool:
    return bool(_COUNTER_RE.match((s or "").strip()))


def _save_to_db(job: frame_job, text: str) -> None:
    if ImageAnnotation.select().where(
        ImageAnnotation.annotation_id == job.frame_id
    ).exists():
        return
    ImageAnnotation.create(
        annotation_id=job.frame_id,
        broadcaster=job.broadcaster,
        room_id=job.room_id or 0,
        time_ms=job.time_ms,
        annotation=text,
    )


async def summarize(job: frame_job, sess: aiohttp.ClientSession) -> str:
    base_url = "http://127.0.0.1:8080"
    url = f"{base_url}/v1/chat/completions"

    b = await asyncio.to_thread(job.path.read_bytes)
    img_url = "data:image/jpeg;base64," + base64.b64encode(b).decode("ascii")

    instr = (
        "You see ONE frame from a Twitch livestream. Focus on the streamer and what they are doing right now.\n"
        "Write a compact, information-dense summary of what is happening RIGHT NOW.\n"
        "3–5 sentences, <= 500 characters. Plain text only (no markdown, no JSON).\n"
        "Prioritize the streamer: their activity, posture/gesture, and on-screen interaction.\n"
        "If visible, mention: main activity + webcam presence + chat + overlays/HUD.\n"
        "Name the game/app if obvious; otherwise say 'unknown game/app'.\n"
        "Be strictly factual; no guesses, no viewer commands, no timestamps.\n"
        "Never invent unreadable text; say 'text unclear' if needed.\n"
    )

    payload = {
        "model": "SmolVLM-1.7B-Instruct",
        "messages": [
            {"role": "system", "content": "Return only the summary text."},
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": instr},
                    {"type": "image_url", "image_url": {"url": img_url}},
                ],
            },
        ],
        "temperature": 0.2,
        "max_tokens": 180,
    }

    last_err: tp.Optional[Exception] = None
    for _ in range(4):
        try:
            async with sess.post(url, json=payload) as r:
                t = await r.text()
                if r.status != 200:
                    raise RuntimeError(f"http {r.status}: {t[:200]}")
                data = json.loads(t)
            out = _clean(_extract_content(data))
            if out and _looks_like_counter(out):
                last_err = RuntimeError(f"invalid_output: {out}")
                out = ""
            if out:
                return out
        except Exception as e:
            last_err = e
        await asyncio.sleep(0.5 + random.random() * 0.2)

    return _clean(f"summary_error: {repr(last_err) if last_err else 'unknown'}")


async def worker(q: asyncio.Queue, sem: asyncio.Semaphore, wid: int) -> None:
    logger.info("Worker %d started", wid)
    timeout = aiohttp.ClientTimeout(total=90)
    async with aiohttp.ClientSession(timeout=timeout) as sess:
        while True:
            job: frame_job = await q.get()
            try:
                async with sem:
                    text = await summarize(job, sess)
                await asyncio.to_thread(_save_to_db, job, text)
                logger.info("saved %s %s", job.frame_id, text[:100])
            except Exception as e:
                logger.error("worker %d failed for %s: %r", wid, getattr(job, "frame_id", "?"), e)
            finally:
                q.task_done()


def start_workers(q: asyncio.Queue, n: int = 4, max_inflight: int = 2) -> list[asyncio.Task]:
    sem = asyncio.Semaphore(max_inflight)
    return [asyncio.create_task(worker(q, sem, i)) for i in range(n)]
