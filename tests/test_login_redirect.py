"""Regression tests: the Xiaomi login redirect `location` is server-controlled
input and must be validated against an allowlist of Xiaomi-owned HTTPS hosts
before it is followed (SSRF / credential-leak guard).
"""

from __future__ import annotations

import asyncio
import base64
import json

import httpx
import pytest

from mi_fitness_mcp.adapters.mi_fitness_cloud import (
    LOGIN_PREFIX,
    MiFitnessCloudAdapter,
    _is_allowed_login_redirect,
)


@pytest.mark.parametrize(
    "url",
    [
        "https://account.xiaomi.com/pass/serviceLoginAuth2",
        "https://sts.api.mi.com/x",
        "https://xiaomi.com/",
        "https://mi.com/",
    ],
)
def test_login_redirect_allowlist_accepts_xiaomi_https(url):
    assert _is_allowed_login_redirect(url) is True


@pytest.mark.parametrize(
    "url",
    [
        "http://evil.com",
        "http://account.xiaomi.com/pass/serviceLoginAuth2",  # plain HTTP
        "https://evil.com",
        "https://xiaomi.com.evil.com/x",  # lookalike suffix attack
        "https://notmi.com/x",
        "not-a-url",
        "",
    ],
)
def test_login_redirect_allowlist_rejects_untrusted(url):
    assert _is_allowed_login_redirect(url) is False


class _FakeResponse:
    def __init__(self, text: str = "", headers: httpx.Headers | None = None):
        self.text = text
        self.headers = headers or httpx.Headers()

    def raise_for_status(self) -> None:
        return None


class _RecordingClient:
    """Serves a synthetic login payload, then records any redirect request."""

    def __init__(self, login_location: str):
        self.requested_urls: list[str] = []
        payload = {
            "passToken": "synthetic-new-token",
            "userId": 12345,
            "ssecurity": base64.b64encode(b"synthetic-ssecurity").decode(),
            "location": login_location,
        }
        self._login_text = LOGIN_PREFIX.decode() + json.dumps(payload)

    async def get(self, url: str, **kwargs) -> _FakeResponse:
        self.requested_urls.append(url)
        if "serviceLogin" in url:
            return _FakeResponse(text=self._login_text)
        return _FakeResponse(
            headers=httpx.Headers({"set-cookie": "serviceToken=abc; Path=/"})
        )


def test_login_rejects_malicious_redirect_without_following_it():
    adapter = MiFitnessCloudAdapter(user_id="synthetic-user", pass_token="synthetic-token")
    client = _RecordingClient("http://evil.com/steal?c=1")
    adapter._client = client

    with pytest.raises(RuntimeError, match="Refusing untrusted login redirect"):
        asyncio.run(adapter._login_with_token("synthetic-user", "synthetic-token"))

    # Only the initial serviceLogin request may have happened.
    assert len(client.requested_urls) == 1
    assert "serviceLogin" in client.requested_urls[0]


def test_login_follows_allowed_xiaomi_redirect():
    adapter = MiFitnessCloudAdapter(user_id="synthetic-user", pass_token="synthetic-token")
    client = _RecordingClient("https://sts.api.mi.com/auth2")
    adapter._client = client

    asyncio.run(adapter._login_with_token("synthetic-user", "synthetic-token"))

    assert client.requested_urls[-1] == "https://sts.api.mi.com/auth2"
    assert adapter._cookies == "serviceToken=abc"
    assert adapter.pass_token == "synthetic-new-token"
