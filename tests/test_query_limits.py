"""Regression tests: list-query limits are enforced in SQL (not by loading the
full table and slicing in Python), and queries without an explicit limit are
capped by DEFAULT_QUERY_LIMIT so an agent cannot pull an entire table.
"""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from mi_fitness_mcp.models import (
    AbnormalHeartBeatEvent,
    HeartRateSample,
    SpO2Sample,
    StressSample,
)
from mi_fitness_mcp.services import query_service
from mi_fitness_mcp.services.query_service import QueryService
from mi_fitness_mcp.storage import Database

USER_ID = "synthetic-limit-user"
BASE_TIME = datetime(2026, 7, 15, 8, 0, 0)
BASE = {"provider": "mi_fitness", "source_type": "cloud_session", "user_id": USER_ID}


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "limits.db")


@pytest.fixture
def service(db):
    return QueryService(db, USER_ID)


def _seed_heart_rate(db: Database, count: int, sample_type: str = "passive") -> None:
    db.insert_heart_rate_samples(
        [
            HeartRateSample(
                id=f"hr-{sample_type}-{i}",
                timestamp=BASE_TIME + timedelta(seconds=i),
                bpm=60 + (i % 40),
                sample_type=sample_type,
                **BASE,
            )
            for i in range(count)
        ]
    )


def test_heart_rate_limit_is_applied(db, service):
    _seed_heart_rate(db, 10)
    samples = service.get_heart_rate_samples("2026-07-15", "2026-07-15", limit=3)
    assert len(samples) == 3
    # Ordered by timestamp ascending: the first three samples come back.
    assert [s["bpm"] for s in samples] == [60, 61, 62]


def test_heart_rate_default_cap_applies_without_limit(db, service, monkeypatch):
    monkeypatch.setattr(query_service, "DEFAULT_QUERY_LIMIT", 4)
    _seed_heart_rate(db, 10)
    samples = service.get_heart_rate_samples("2026-07-15", "2026-07-15")
    assert len(samples) == 4


def test_heart_rate_sample_type_filter_combined_with_limit(db, service):
    _seed_heart_rate(db, 5, sample_type="passive")
    _seed_heart_rate(db, 5, sample_type="active")
    samples = service.get_heart_rate_samples(
        "2026-07-15", "2026-07-15", sample_type="active", limit=2
    )
    assert len(samples) == 2
    assert all(s["sample_type"] == "active" for s in samples)


def test_spo2_default_cap_applies_without_limit(db, service, monkeypatch):
    monkeypatch.setattr(query_service, "DEFAULT_QUERY_LIMIT", 3)
    db.insert_spo2_sample(
        SpO2Sample(id="spo2-extra", timestamp=BASE_TIME + timedelta(hours=1), spo2_pct=98, **BASE)
    )
    for i in range(5):
        db.insert_spo2_sample(
            SpO2Sample(
                id=f"spo2-{i}", timestamp=BASE_TIME + timedelta(seconds=i), spo2_pct=95 + i, **BASE
            )
        )
    samples = service.get_spo2_samples("2026-07-15", "2026-07-15")
    assert len(samples) == 3


def test_stress_level_filter_and_limit(db, service):
    for i, (score, level) in enumerate([(10, "low"), (40, "medium"), (80, "high"), (90, "high")]):
        db.insert_stress_sample(
            StressSample(
                id=f"stress-{i}",
                timestamp=BASE_TIME + timedelta(seconds=i),
                stress_score=score,
                level=level,
                **BASE,
            )
        )
    samples = service.get_stress_samples("2026-07-15", "2026-07-15", level="high", limit=1)
    assert len(samples) == 1
    assert samples[0]["level"] == "high"
    assert samples[0]["stress_score"] == 80  # earliest matching row


def test_abnormal_heart_beat_limit(db, service):
    for i in range(4):
        start = BASE_TIME + timedelta(minutes=i)
        db.insert_abnormal_heart_beat_event(
            AbnormalHeartBeatEvent(
                id=f"ahb-{i}",
                event_id=f"ev-{i}",
                start_at=start,
                end_at=start + timedelta(seconds=30),
                duration_seconds=30,
                **BASE,
            )
        )
    events = service.get_abnormal_heart_beat_events("2026-07-15", "2026-07-15", limit=2)
    assert len(events) == 2
    assert [e["event_id"] for e in events] == ["ev-0", "ev-1"]
