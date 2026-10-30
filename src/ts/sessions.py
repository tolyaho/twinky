"""Bounded single-process beta API/worker controller. No public billing guarantee.

No queue beyond one reserved active job. Restarting resets the admission counters; a shared,
provider-backed quota service is required before scaling or exposing arbitrary public traffic.
"""
from __future__ import annotations
from collections import defaultdict, deque
from dataclasses import dataclass, field
import hmac
import json
import os
from pathlib import Path
import queue
import secrets
import signal
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlsplit
from .live_limits import LIMITS
from .twitch import TwitchUnavailable, channel_name

TERMINAL = frozenset({"offline", "not_found", "unavailable", "failed", "timed_out", "cancelled", "completed"})
EVENT_TYPES = frozenset({"status", "progress", "context", "candidate_signal", "provenance_decision", "error", "completion"})


class AdmissionError(ValueError):
    def __init__(self, code, status=429):
        super().__init__(code)
        self.status = status


@dataclass
class Config:
    enabled: bool = False
    token: str = field(default="", repr=False)
    starts: int = 0  # operator must explicitly reserve startup credits; no automatic reset
    allowed_ips: tuple = ("127.0.0.1", "::1")
    evidence_text: bool = False

    @classmethod
    def from_env(cls):
        try:
            starts = int(os.getenv("TWINKY_SESSION_CREDITS", "0"))
        except ValueError:
            starts = 0
        return cls(os.getenv("TWINKY_LIVE_ENABLED") == "1",
                   os.getenv("TWINKY_DEMO_ACCESS_TOKEN", ""), min(20, max(0, starts)),
                   tuple(x.strip() for x in os.getenv("TWINKY_ALLOWED_IPS", "127.0.0.1,::1").split(",") if x.strip()),
                   os.getenv("TWINKY_EVIDENCE_TEXT") == "1")


@dataclass
class Job:
    id: str
    channel: str
    created: float
    source_mode: str
    state: str = "queued"
    events: list = field(default_factory=list)
    result: dict | None = None
    cancel: threading.Event = field(default_factory=threading.Event, repr=False)
    done: threading.Event = field(default_factory=threading.Event, repr=False)
    lock: threading.RLock = field(default_factory=threading.RLock, repr=False)


class SessionManager:
    def __init__(self, config=None, *, lookup=None, processor=None, source_mode="live"):
        self.config = config or Config.from_env()
        self.lookup = lookup  # Only injected by offline tests. Production lookup runs in child.
        self.processor = processor or self._subprocess
        self.source_mode = source_mode
        self.jobs = {}
        self._lock = threading.Lock()
        self._active = 0
        self._used = 0
        self._rates = defaultdict(deque)

    def authorize(self, header, peer):
        cfg = self.config
        if not cfg.enabled or len(cfg.token) < 32 or cfg.starts < 1:
            raise AdmissionError("live_not_configured", 503)
        if peer not in cfg.allowed_ips:
            raise AdmissionError("ip_not_allowed", 403)
        expected = ("Bearer " + cfg.token).encode()
        if not hmac.compare_digest(str(header or "").encode(), expected):
            raise AdmissionError("authentication_required", 401)

    def start(self, channel, peer, duration_seconds=60):
        channel = channel_name(channel)
        if type(duration_seconds) is not int or duration_seconds != LIMITS.capture_seconds:
            raise AdmissionError("duration_seconds_must_be_60", 400)
        with self._lock:
            now = time.monotonic()
            # Prune jobs (15 minute retention); never prune an active worker.
            self.jobs = {k: j for k, j in self.jobs.items() if not j.done.is_set() or now-j.created < 900}
            rates = self._rates[peer]
            while rates and rates[0] < now - 3600:
                rates.popleft()
            if len(rates) >= 2:
                raise AdmissionError("ip_rate_limit")
            if self._active:
                raise AdmissionError("capacity_unavailable", 503)
            if self._used >= self.config.starts or len(self.jobs) >= 20:
                raise AdmissionError("startup_credits_exhausted", 503)
            rates.append(now)
            self._active += 1
            self._used += 1  # reserved before lookup/spawn; never refunded on error or cancel
            job = Job(secrets.token_urlsafe(18), channel, now, self.source_mode)
            self.jobs[job.id] = job
            self._emit(job, "status", {"state": "queued"})
            threading.Thread(target=self._run, args=(job,), daemon=True).start()
            return job

    def get(self, job_id):
        with self._lock:
            job = self.jobs.get(job_id)
        if job is None or (job.done.is_set() and time.monotonic()-job.created >= 900):
            raise AdmissionError("session_not_found", 404)
        return job

    def _safe(self, value):
        if isinstance(value, list):
            return [self._safe(v) for v in value]
        if isinstance(value, dict):
            return {k: ("[withheld pending rights/privacy review]" if
                        not self.config.evidence_text and k in {"text", "title", "quote", "detail", "distribution"}
                        else self._safe(v)) for k, v in value.items()
                    if k not in {"author", "login", "trace_path"}}
        return value

    def _emit(self, job, kind, data):
        if kind not in EVENT_TYPES:
            raise ValueError("invalid_session_event")
        with job.lock:
            if len(job.events) >= LIMITS.max_events - 2 and kind not in {"completion", "error"}:
                raise RuntimeError("event_limit")
            event = {"schema_version": 1, "session_id": job.id, "seq": len(job.events)+1,
                     "type": kind, "elapsed_ms": int((time.monotonic()-job.created)*1000),
                     "source_mode": job.source_mode, "data": self._safe(data)}
            if len(json.dumps(event).encode()) > LIMITS.max_event_bytes:
                raise RuntimeError("event_size_limit")
            job.events.append(event)
            return event

    def _state(self, job, state):
        with job.lock:
            job.state = state
        self._emit(job, "status", {"state": state})

    def _run(self, job):
        state = "failed"
        try:
            self._state(job, "checking")
            if self.lookup is not None:
                status = self.lookup(job.channel)
                self._emit(job, "context", {"channel_status": status})
                if not status.get("live"):
                    state = status["state"]
                    return
                self._state(job, "running")
            result = self._safe(self.processor(job, lambda k, d: self._emit(job, k, d)))
            if len(json.dumps(result).encode()) > LIMITS.max_event_bytes // 2:
                raise RuntimeError("result_size_limit")
            job.result = result
            state = "cancelled" if job.cancel.is_set() else "completed"
            if isinstance(job.result, dict) and job.result.get("terminal_state") in TERMINAL:
                state = job.result.pop("terminal_state")
        except TwitchUnavailable:
            state = "unavailable"
            self._emit(job, "error", {"code": "twitch_unavailable"})
        except TimeoutError:
            state = "timed_out"
            self._emit(job, "error", {"code": "session_deadline"})
        except InterruptedError:
            state = "cancelled"
        except Exception:
            self._emit(job, "error", {"code": "worker_failed"})
        finally:
            # Processor returns only after its process group is killed/waited and scratch removed.
            with job.lock:
                job.state = state
                self._emit(job, "completion", {"state": state, "result": job.result})
            with self._lock:
                self._active -= 1
            job.done.set()

    def snapshot(self, job):
        with job.lock:
            return {"schema_version": 1, "session_id": job.id, "channel": job.channel,
                    "state": job.state, "source_mode": job.source_mode,
                    "last_seq": len(job.events), "result": job.result,
                    "limits": LIMITS.public(), "evidence_text": self.config.evidence_text}

    @staticmethod
    def _stop(proc):
        # All descendants (including ffmpeg) share this fresh POSIX process group.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait(timeout=5)

    def _subprocess(self, job, emit):
        names = ("PATH", "HOME", "LANG", "SSL_CERT_FILE", "TWITCH_CLIENT_ID", "TWITCH_CLIENT_SECRET",
                 "TWITCH_APP_ACCESS_TOKEN", "TS_LLM_BASE_URL", "TS_LLM_API_KEY", "TS_TEXT_MODEL",
                 "DEEPSEEK_API_KEY", "DEEPGRAM_API_KEY")
        env = {k: os.environ[k] for k in names if k in os.environ}
        # A default GPT model and a default DeepSeek endpoint are incompatible. Require explicit routing.
        if (not env.get("TS_LLM_BASE_URL") or urlsplit(env["TS_LLM_BASE_URL"]).scheme != "https" or
            not (env.get("TS_LLM_API_KEY") or env.get("DEEPSEEK_API_KEY")) or
            not env.get("DEEPGRAM_API_KEY")):
            return {"terminal_state": "unavailable", "code": "providers_not_configured"}
        env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        with tempfile.TemporaryDirectory(prefix="twinky-job-") as scratch:
            os.chmod(scratch, 0o700)
            proc = subprocess.Popen([sys.executable, "-m", "ts.live_worker", job.channel],
                                    cwd=scratch, env=env, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, start_new_session=True)
            messages = queue.Queue(maxsize=16)
            def read():
                try:
                    while True:
                        line = proc.stdout.readline(LIMITS.max_event_bytes + 1)
                        messages.put(line)
                        if not line:
                            break
                except (OSError, ValueError):
                    pass
            reader = threading.Thread(target=read, daemon=True)
            reader.start()
            result = None
            try:
                while True:
                    if job.cancel.is_set():
                        raise InterruptedError()
                    if time.monotonic() - job.created > LIMITS.session_seconds:
                        raise TimeoutError()
                    if sum(p.stat().st_size for p in Path(scratch).rglob("*") if p.is_file()) > LIMITS.max_disk_bytes:
                        raise RuntimeError("disk_limit")
                    try:
                        line = messages.get(timeout=.1)
                    except queue.Empty:
                        continue
                    if not line:
                        break
                    if len(line) > LIMITS.max_event_bytes:
                        raise RuntimeError("worker_protocol_limit")
                    message = json.loads(line)
                    kind, data = message["type"], message["data"]
                    if kind == "worker_result":
                        result = data
                    elif kind == "worker_terminal":
                        result = {"terminal_state": data["state"]}
                    elif kind == "status":
                        self._state(job, data["state"])
                    else:
                        emit(kind, data)
                proc.wait(timeout=5)
                if proc.returncode or result is None:
                    raise RuntimeError("worker_exit")
                return result
            finally:
                # Kill descendants even if the worker parent exited normally.
                self._stop(proc)
                proc.stdout.close()
                # Drain a blocked reader before joining; its queue is deliberately bounded.
                while reader.is_alive():
                    try:
                        messages.get(timeout=.1)
                    except queue.Empty:
                        pass
                    reader.join(timeout=.1)

    def close(self):
        with self._lock:
            jobs = list(self.jobs.values())
        for job in jobs:
            if not job.done.is_set():
                job.cancel.set()
        for job in jobs:
            job.done.wait(timeout=5)
