from __future__ import annotations

import asyncio

import httpx

from mi_fitness_mcp.adapters.mi_fitness_cloud import MiFitnessCloudAdapter


class _OfflineAsyncClient:
    """Captures constructor kwargs and fails every request without network."""

    captured_kwargs: list[dict] = []

    def __init__(self, **kwargs):
        type(self).captured_kwargs.append(kwargs)

    async def get(self, *args, **kwargs):
        raise httpx.ConnectError("offline test double")

    async def aclose(self):
        return None


def test_cloud_adapter_builds_client_with_trust_env_disabled(monkeypatch):
    """小米云是国内服务，客户端必须 trust_env=False 直连，不受系统代理状态影响。"""
    _OfflineAsyncClient.captured_kwargs = []
    monkeypatch.setattr(httpx, "AsyncClient", _OfflineAsyncClient)

    adapter = MiFitnessCloudAdapter(user_id="synthetic-user", pass_token="synthetic-token")
    connected = asyncio.run(adapter.connect())

    assert connected is False  # 离线替身必然登录失败，但客户端构造参数已捕获
    assert len(_OfflineAsyncClient.captured_kwargs) == 1
    assert _OfflineAsyncClient.captured_kwargs[0]["trust_env"] is False
