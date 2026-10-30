"""Official Helix lookup. Credentials and OAuth responses never enter public events."""
from __future__ import annotations
import os
import re
import threading
import time


def channel_name(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-zA-Z0-9_]{1,25}", value):
        raise ValueError("channel must be a Twitch username (1-25 letters, digits or underscore)")
    return value.lower()


class TwitchUnavailable(RuntimeError):
    pass


class TwitchStatus:
    def __init__(self, client_id=None, client_secret=None, access_token=None, transport=None):
        self._client_id = client_id or os.getenv("TWITCH_CLIENT_ID")
        self._secret = client_secret or os.getenv("TWITCH_CLIENT_SECRET")
        self._token = access_token or os.getenv("TWITCH_APP_ACCESS_TOKEN")
        self._expires = float("inf") if self._token else 0
        self._lock = threading.Lock()
        self._transport = transport

    def _request(self, method, url, **kwargs):
        if self._transport:
            return self._transport(method, url, **kwargs)
        import httpx
        with httpx.Client(timeout=10, trust_env=False, follow_redirects=False) as client:
            response = client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()

    def lookup(self, channel):
        channel = channel_name(channel)
        with self._lock:
            try:
                if not self._client_id:
                    raise TwitchUnavailable("twitch_not_configured")
                if time.monotonic() >= self._expires:
                    if not self._secret:
                        raise TwitchUnavailable("twitch_not_configured")
                    token = self._request("POST", "https://id.twitch.tv/oauth2/token", data={
                        "client_id": self._client_id, "client_secret": self._secret,
                        "grant_type": "client_credentials"})
                    self._token = token["access_token"]
                    self._expires = time.monotonic() + max(0, int(token["expires_in"]) - 60)
                headers = {"Client-Id": self._client_id, "Authorization": f"Bearer {self._token}"}
                users = self._request("GET", "https://api.twitch.tv/helix/users",
                                      params={"login": channel}, headers=headers)["data"]
                if not users:
                    return {"channel": channel, "state": "not_found", "exists": False, "live": False}
                streams = self._request("GET", "https://api.twitch.tv/helix/streams",
                                        params={"user_id": users[0]["id"]}, headers=headers)["data"]
                return {"channel": channel, "state": "live" if streams else "offline",
                        "exists": True, "live": bool(streams)}
            except TwitchUnavailable:
                raise
            except Exception:
                # Neither HTTP exception URLs nor upstream bodies are safe public errors.
                self._expires = 0
                raise TwitchUnavailable("twitch_lookup_failed") from None
