"""Regression tests for the agent-safe workout_series pipeline (issue #5).

Uses only the synthetic 3-hour ride fixture from tests/synthetic_fixtures.py
(issue #6): 10,800 1 Hz heart rate points with known ground-truth statistics.
"""

from __future__ import annotations

import asyncio
import json
import statistics

import pytest

from mi_fitness_mcp import server
from mi_fitness_mcp.services.query_service import (
    HARD_MAX_POINTS,
    ZONE_FRACTIONS,
    QueryService,
)
from mi_fitness_mcp.storage import Database
from tests.synthetic_fixtures import (
    SYNTHETIC_RIDE_WORKOUT_ID,
    SYNTHETIC_USER_ID,
    seed_synthetic_ride,
)


@pytest.fixture
def seeded_db(tmp_path):
    db = Database(tmp_path / "synthetic.db")
    bpms = seed_synthetic_ride(db)
    return db, bpms


@pytest.fixture
def service(seeded_db):
    db, _ = seeded_db
    return QueryService(db, SYNTHETIC_USER_ID)


def ground_truth_zone_seconds(bpms: list[int]) -> list[int]:
    reference_max = max(bpms)
    bounds = [int(reference_max * f) for f in ZONE_FRACTIONS]
    zones = [0] * (len(bounds) + 1)
    for bpm in bpms:
        zones[sum(bpm >= bound for bound in bounds)] += 1  # 1 Hz: 1 sample == 1 s
    return zones


def test_downsampled_series_metadata_and_stats(service, seeded_db):
    _, bpms = seeded_db
    result = service.get_workout_series(SYNTHETIC_RIDE_WORKOUT_ID)

    assert result["downsampled"] is True
    assert result["method"] == "time_bucket_mean"
    assert result["source_points"] == 10_800
    assert 0 < result["returned_points"] <= 400
    assert result["returned_points"] == len(result["points"])

    # Summary stats are computed on the full-resolution series (ground truth).
    stats = result["stats"]
    assert abs(stats["avg"] - statistics.fmean(bpms)) <= 1.0
    assert stats["min"] == min(bpms)
    assert stats["max"] == max(bpms)
    assert stats["p25"] <= stats["p50"] <= stats["p75"]

    # Bucket means stay faithful to the raw average.
    bucket_avg = statistics.fmean(p["value"] for p in result["points"])
    assert abs(bucket_avg - statistics.fmean(bpms)) <= 1.0

    # Time-in-zone matches the ground-truth zone distribution (1 Hz samples).
    truth = ground_truth_zone_seconds(bpms)
    zones = result["time_in_zone"]["zones"]
    assert [z["seconds"] for z in zones] == truth
    assert sum(z["seconds"] for z in zones) == len(bpms)


def test_max_points_is_hard_capped(service):
    result = service.get_workout_series(SYNTHETIC_RIDE_WORKOUT_ID, max_points=10_000)
    assert result["downsampled"] is True
    assert result["returned_points"] <= HARD_MAX_POINTS


def test_requested_resolution_honored_when_within_budget(service):
    result = service.get_workout_series(
        SYNTHETIC_RIDE_WORKOUT_ID, resolution=60, max_points=500
    )
    # 3h / 60s = 180 buckets, within budget: keep the requested resolution.
    assert result["resolution_seconds"] == 60
    assert result["returned_points"] == 180


def test_adaptive_resolution_when_budget_too_small(service):
    result = service.get_workout_series(
        SYNTHETIC_RIDE_WORKOUT_ID, resolution=10, max_points=300
    )
    assert result["resolution_seconds"] >= 36  # ceil(10800 / 300)
    assert result["returned_points"] <= 300


def test_short_workout_is_returned_at_full_resolution(tmp_path):
    db = Database(tmp_path / "synthetic.db")
    bpms = seed_synthetic_ride(db, workout_id="synthetic-ride-short", duration_seconds=300)
    service = QueryService(db, SYNTHETIC_USER_ID)

    result = service.get_workout_series("synthetic-ride-short")
    assert result["downsampled"] is False
    assert result["method"] == "none"
    assert result["source_points"] == 300
    assert result["returned_points"] == 300
    assert [p["value"] for p in result["points"]] == bpms


def test_unknown_workout_raises(service):
    with pytest.raises(ValueError, match="Unknown workout_id"):
        service.get_workout_series("no-such-workout")


def test_unsupported_metric_raises(service):
    with pytest.raises(ValueError, match="Unsupported workout metric"):
        service.get_workout_series(SYNTHETIC_RIDE_WORKOUT_ID, metric="power")


def test_server_tool_roundtrip(service, monkeypatch):
    monkeypatch.setattr(server, "query_service", service)
    tools = asyncio.run(server.list_tools())
    assert "workout_series" in {tool.name for tool in tools}

    content = asyncio.run(
        server.call_tool(
            "workout_series", {"workout_id": SYNTHETIC_RIDE_WORKOUT_ID, "max_points": 400}
        )
    )
    payload = json.loads(content[0].text)
    assert payload["status"] == "ok"
    data = payload["data"]
    assert data["downsampled"] is True
    assert data["source_points"] == 10_800
    assert data["returned_points"] <= 400
    assert data["method"] == "time_bucket_mean"

    error = asyncio.run(server.call_tool("workout_series", {"workout_id": "missing"}))
    assert json.loads(error[0].text)["status"] == "error"


def test_query_workouts_reports_data_quality(service, monkeypatch):
    monkeypatch.setattr(server, "query_service", service)
    content = asyncio.run(
        server.call_tool("query_workouts", {"start_date": "2026-07-15", "end_date": "2026-07-15"})
    )
    payload = json.loads(content[0].text)
    assert payload["status"] == "ok"
    assert payload["data"]["count"] == 1
    quality = payload["data"]["data_quality"]
    assert quality["data_type"] == "workouts"
    assert quality["days_with_data"] == 1
    assert quality["missing_metrics"] == []
