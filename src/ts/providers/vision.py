"""Frame-caption adapter: a hosted VLM over `raw/frames/*.jpg`.

`deepseek-v4-flash` is TEXT ONLY, so captions go to `deepseek-v4-flash-vision-exp`. If it fails
on the eval, swap the model here rather than bending the product around it.

`record` mode only. As with STT the cache key names the image by SHA-256: base64 of a frame is
~100 KB and the cache is committed.
"""
from __future__ import annotations

import base64
from pathlib import Path
from typing import Any, Dict, Optional

from .base import DeepSeekProvider, TextProvider, extract_content

MODEL = "deepseek-v4-flash-vision-exp"
MAX_TOKENS = 300
MAX_CAPTION_CHARS = 500

# Factual, bounded, and explicitly allowed to refuse. A caption is stream *context* that chat is
# grounded against; a hallucinated on-screen number becomes a hallucinated trigger downstream.
FRAME_PROMPT = (
    "Describe this livestream frame factually in at most 500 characters: the game or scene, "
    "what the streamer is doing, visible on-screen text and HUD numbers, and anything a viewer "
    "would plausibly react to. Do not interpret, do not speculate about intent. If text is too "
    "small or blurred to read, write \"text unclear\" rather than inventing it. Reply with the "
    "description only."
)


def build_vision_request(*, image_sha256: str, model: str = MODEL, prompt: str = FRAME_PROMPT,
                         max_tokens: int = MAX_TOKENS,
                         temperature: float = 0.0) -> Dict[str, Any]:
    """Canonical request. This dict IS the cache key. Editing FRAME_PROMPT invalidates every
    cached caption - say so in PROGRESS.md rather than silently re-recording."""
    return {
        "provider": "deepseek-vision",
        "model": model,
        "prompt": prompt,
        "image_sha256": image_sha256,
        "max_tokens": int(max_tokens),
        "temperature": float(temperature),
    }


def wire_request(request: Dict[str, Any], image_b64: str) -> Dict[str, Any]:
    """Cache-key request -> the chat-completions payload actually sent. The image travels here
    and never enters the cache key."""
    return {
        "model": request["model"],
        "temperature": request["temperature"],
        "max_tokens": request["max_tokens"],
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": request["prompt"]},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ],
        }],
    }


class VisionProvider:
    """Bound to one frame, matching the one-argument provider shape `ResponseCache.call`
    expects. Reads the file lazily: a cache hit never opens the jpg."""

    def __init__(self, image_path: Path | str,
                 text_provider: Optional[TextProvider] = None) -> None:
        self.image_path = Path(image_path)
        self.text_provider = text_provider or DeepSeekProvider()

    def __call__(self, request: Dict[str, Any]) -> Dict[str, Any]:
        image_b64 = base64.b64encode(self.image_path.read_bytes()).decode("ascii")
        return self.text_provider.complete(wire_request(request, image_b64))


def caption_from_response(response: Dict[str, Any]) -> str:
    """Whitespace-normalised and hard-capped, so one runaway caption cannot blow up the context
    budget of every downstream window."""
    return " ".join(extract_content(response).split())[:MAX_CAPTION_CHARS]
