"""Operational quotas, not a currency/billing guarantee. Shared by API and worker."""
from dataclasses import dataclass, asdict
import json
from .cache import ResponseCache


@dataclass(frozen=True)
class Limits:
    capture_seconds: int = 60
    session_seconds: int = 180
    max_input_bytes: int = 64 * 1024 * 1024
    max_disk_bytes: int = 16 * 1024 * 1024
    max_audio_bytes: int = 2_000_000
    max_frame_bytes: int = 1_000_000
    max_frames: int = 2
    max_chat: int = 3000
    max_calls: int = 7  # STT 1, captions 2, agent 4
    max_completion_tokens: int = 4200  # 2*300 + 4*900
    max_request_bytes: int = 32_768  # text request, including all tool results
    max_text_input_bytes: int = 131_072
    max_events: int = 128
    max_event_bytes: int = 16_384

    def public(self):
        return asdict(self)


LIMITS = Limits()


class QuotaExceeded(RuntimeError):
    pass


class LimitedCache(ResponseCache):
    """Check and reserve before every request, including cache hits; no automatic retries."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.calls = self.tokens = self.input_bytes = 0
        self.modalities = {"deepgram": 0, "vision": 0, "text": 0}

    def call(self, request, provider):
        kind = request.get("provider", "text")
        if kind not in self.modalities:
            raise QuotaExceeded("unsupported_provider")
        caps = {"deepgram": 1, "vision": 2, "text": 4}
        tokens = int(request.get("max_tokens", 0))
        size = len(json.dumps(request, ensure_ascii=False).encode()) if kind == "text" else 0
        if (tokens < 0 or tokens > (900 if kind == "text" else 300) or
            self.calls >= LIMITS.max_calls or self.modalities[kind] >= caps[kind] or
            self.tokens + tokens > LIMITS.max_completion_tokens or
            size > LIMITS.max_request_bytes or
            self.input_bytes + size > LIMITS.max_text_input_bytes):
            raise QuotaExceeded("provider_quota_exceeded")
        self.calls += 1
        self.modalities[kind] += 1
        self.tokens += tokens
        self.input_bytes += size
        return super().call(request, provider)
