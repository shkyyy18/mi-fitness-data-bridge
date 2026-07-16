from __future__ import annotations

import asyncio

import pytest

from mi_fitness_mcp.services.sync_service import SyncService


class ConnectedAdapter:
    def is_connected(self) -> bool:
        return True


class FakeDatabase:
    def __init__(self, state=None):
        self.state = state

    def get_sync_state(self, data_type):
        return self.state


@pytest.mark.parametrize(
    ("lookback_days", "chunk_days", "message"),
    [
        (0, 7, "default_lookback_days must be at least 1"),
        (30, 0, "chunk_days must be at least 1"),
    ],
)
def test_sync_service_rejects_non_positive_ranges(lookback_days, chunk_days, message):
    with pytest.raises(ValueError, match=message):
        SyncService(
            ConnectedAdapter(),
            FakeDatabase(),
            default_lookback_days=lookback_days,
            chunk_days=chunk_days,
        )


def test_sync_service_chunks_requested_range_and_aggregates_counts():
    service = SyncService(ConnectedAdapter(), FakeDatabase(), chunk_days=3)
    calls: list[tuple[str, str, str]] = []

    async def fake_sync_range(data_type, start_date, end_date):
        calls.append((data_type, start_date, end_date))
        return {"added": 1, "updated": 2, "skipped": 3}

    service._sync_range = fake_sync_range
    result = asyncio.run(
        service.sync_data_type(
            "daily_activity",
            start_date="2026-07-01",
            end_date="2026-07-07",
        )
    )

    assert calls == [
        ("daily_activity", "2026-07-01", "2026-07-03"),
        ("daily_activity", "2026-07-04", "2026-07-06"),
        ("daily_activity", "2026-07-07", "2026-07-07"),
    ]
    assert result["status"] == "ok"
    assert result["added"] == 3
    assert result["updated"] == 6
    assert result["skipped"] == 9
    assert service.sync_in_progress is False


def test_sync_service_returns_partial_result_and_releases_lock_after_chunk_failure():
    service = SyncService(ConnectedAdapter(), FakeDatabase(), chunk_days=2)
    calls = 0

    async def fake_sync_range(data_type, start_date, end_date):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("synthetic chunk failure")
        return {"added": 2, "updated": 1, "skipped": 0}

    service._sync_range = fake_sync_range
    result = asyncio.run(
        service.sync_data_type(
            "daily_activity",
            start_date="2026-07-01",
            end_date="2026-07-05",
        )
    )

    assert result["status"] == "partial"
    assert result["added"] == 2
    assert result["updated"] == 1
    assert result["error_code"] == "RuntimeError"
    assert result["chunks"][1]["status"] == "error"
    assert service.sync_in_progress is False
