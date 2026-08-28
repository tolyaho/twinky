import aiohttp
import asyncio
import json
import logging
import os
import random


def _to_str(x) -> str:
    try:
        return json.dumps(x, ensure_ascii=False)
    except Exception:
        return str(x)


def _extract_content(resp: dict) -> str:
    try:
        result = resp["choices"][0]["message"]["content"]
        if isinstance(result, str):
            return result
        return _to_str(result)
    except Exception:
        return _to_str(resp)


class LlmError(RuntimeError):
    pass


logger = logging.getLogger("chat_summaries.llm")


class LlmClient:
    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        model: str | None = None,
        concurrency: int = 8,
        timeout_s: float = 8.0,
        retries: int = 3,
        backoff_base_s: float = 0.35,
        headers: dict[str, str] | None = None,
    ):
        self.base_url = (base_url or os.getenv("LLM_BASE_URL") or "").rstrip("/")
        if not self.base_url:
            raise ValueError("empty base_url")
        if self.base_url in {"https://api.deepseek.com", "https://api.openai.com"}:
            self.base_url = f"{self.base_url}/v1"

        self.api_key = (api_key or os.getenv("LLM_API_KEY"))
        self.model = model or os.getenv("LLM_MODEL") or "deepseek-chat"
        self.concurrency = concurrency
        self.timeout_s = timeout_s
        self.retries = retries
        self.backoff_base_s = backoff_base_s
        self._hdr = dict(headers or {})
        self._sem = asyncio.Semaphore(self.concurrency)
        self._session: aiohttp.ClientSession | None = None

    async def open(self) -> None:
        if self._session:
            return
        h = {"content-type": "application/json"}
        if self.api_key:
            h["authorization"] = f"Bearer {self.api_key}"
        
        h.update(self._hdr)
        to = aiohttp.ClientTimeout(total=self.timeout_s)
        conn = aiohttp.TCPConnector(limit=self.concurrency, ttl_dns_cache=300)
        self._session = aiohttp.ClientSession(headers=h, timeout=to, connector=conn)

    async def close(self) -> None:
        if self._session:
            await self._session.close()
        self._session = None

    async def __aenter__(self) -> "LlmClient":
        await self.open()
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        await self.close()

    async def complete(
        self,
        *,
        system_msg: str,
        user_msg: str,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        response_format: dict | None = None,
        extra: dict | None = None
    ) -> dict:
        await self.open()
        assert self._session is not None

        payload = {
            "model": model or self.model,
            "messages": [
                {
                    "role": "system", "content": system_msg
                },
                {
                    "role": "user", "content": user_msg
                }
            ],
            "temperature": float(temperature),
        }
        if extra:
            payload.update(extra)
        if max_tokens is not None:
            payload["max_tokens"] = int(max_tokens)
        if response_format is not None:
            payload["response_format"] = response_format

        url = f"{self.base_url}/chat/completions"
        
        err: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                async with self._sem:
                    async with self._session.post(url, json=payload) as r:
                        txt = await r.text()
                        if r.status >= 400:
                            logger.error("LLM error %s from %s: %s", r.status, url, txt[:2000])
                            raise LlmError(f"http {r.status}: {txt[:700]}")
                        try:
                            resp = json.loads(txt)
                        except json.JSONDecodeError as e:
                            logger.error("LLM invalid JSON from %s: %s", url, txt[:2000])
                            raise LlmError("invalid json response") from e
                        if not isinstance(resp, dict):
                            raise LlmError("unexpected response type")
                        return resp
            except Exception as e:
                err = e
                if attempt >= self.retries:
                    break
                d = self.backoff_base_s * (2 ** attempt) + random.random() * 0.15
                await asyncio.sleep(d)

        if err:
            logger.error(
                "LLM request failed after %d attempts to %s: %r",
                attempt + 1,
                url,
                err,
                exc_info=err,
            )
        raise LlmError(str(err) if err else "llm error")

    async def content(
        self,
        *,
        json_mode: bool = False,
        system_msg: str,
        user_msg: str,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
        response_format: dict | None = None,
        extra: dict | None = None
    ):
        resp = await self.complete(
            system_msg=system_msg,
            user_msg=user_msg,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
            response_format= {"type": "json_object"} if json_mode else response_format,
            extra=extra
        )
        result = _extract_content(resp)
        maybe_json: object | None = None

        if json_mode:
            try:
                obj = json.loads(result)
                maybe_json = obj
            except Exception:
                maybe_json = None
        return result, maybe_json, resp

    async def batch(
        self,
        reqs: list[dict]
    ):
        async def run_one(d: dict):
            d = dict(d)

            # since OpenAI preferred format can be "user" and "system" instead of "user_msg" and "system_msg"
            if "system_msg" not in d and "system" in d:
                d["system_msg"] = d.pop("system")
            if "user_msg" not in d and "user" in d:
                d["user_msg"] = d.pop("user")
            return await self.content(**d)

        return await asyncio.gather(*(run_one(x) for x in reqs))
