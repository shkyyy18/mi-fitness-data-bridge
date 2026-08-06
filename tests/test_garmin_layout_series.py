"""Cross-format regression tests: same 3-hour ride in Mi and Garmin layouts.

Agreed with davidmosiah/garmin-mcp in issue #19: the synthetic ride from
tests/synthetic_fixtures.py also exists as a Garmin-layout payload
(tests/garmin_fixtures.py), and both layouts must produce identical stats
and downsampled points through the same pipeline. Ground truth is computed
straight from the closed-form profile, never from the code under test.
"""

from __future__ import annotations

import math
import statistics

import pytest

from mi_fitness_mcp.services.query_service import QueryService
from mi_fitness_mcp.storage import Database
from tests.garmin_fixtures import (
    GARMIN_RIDE_WORKOUT_ID,
    build_garmin_ride,
    parse_garmin_heart_rate,
    seed_garmin_ride,
)
from tests.synthetic_fixtures import (
    SYNTHETIC_RIDE_WORKOUT_ID,
    SYNTHETIC_USER_ID,
    seed_synthetic_ride,
    synthetic_ride_bpms,
)

STAT_KEYS = ("avg", "min", "max", "p25", "p50", "p75")


def ground_truth_stats(bpms: list[int]) -> dict[str, float]:
    """Stats computed independently from the profile (linear interpolation)."""
    ordered = sorted(bpms)

    def percentile(q: float) -> float:
        rank = (len(ordered) - 1) * q
        low = math.floor(rank)
        high = math.ceil(rank)
        if low == high:
            return ordered[low]
        return ordered[low] + (ordered[high] - ordered[low]) * (rank - low)

    return {
        "avg": sum(bpms) / len(bpms),
        "min": ordered[0],
        "max": ordered[-1],
        "p25": percentile(0.25),
        "p50": percentile(0.5),
        "p75": percentile(0.75),
    }


def assert_stats_match_truth(stats: dict, bpms: list[int]) -> None:
    truth = ground_truth_stats(bpms)
    assert stats["min"] == truth["min"]
    assert stats["max"] == truth["max"]
    # Implementation rounds to 1 decimal; allow that rounding error only.
    for key in ("avg", "p25", "p50", "p75"):
        assert stats[key] == pytest.approx(truth[key], abs=0.06)


def test_garmin_layout_matches_mi_layout(tmp_path):
    mi_db = Database(tmp_path / "mi.db")
    bpms = seed_synthetic_ride(mi_db)
    mi_result = QueryService(mi_db, SYNTHETIC_USER_ID).get_workout_series(
        SYNTHETIC_RIDE_WORKOUT_ID
    )

    garmin_db = Database(tmp_path / "garmin.db")
    # GPS + power columns included: parsing must key off metricDescriptors.
    seed_garmin_ride(garmin_db, include_gps=True)
    garmin_result = QueryService(garmin_db, SYNTHETIC_USER_ID).get_workout_series(
        GARMIN_RIDE_WORKOUT_ID
    )

    # Same ride, two layouts: stats and downsampled points must be identical.
    for key in STAT_KEYS:
        assert garmin_result["stats"][key] == mi_result["stats"][key]
    assert garmin_result["points"] == mi_result["points"]
    assert garmin_result["source_points"] == mi_result["source_points"] == 10_800
    assert garmin_result["downsampled"] is True
    assert garmin_result["method"] == "time_bucket_mean"

    # And both still match ground truth from the profile itself.
    assert_stats_match_truth(garmin_result["stats"], bpms)
    assert_stats_match_truth(mi_result["stats"], bpms)


def test_garmin_layout_with_gap_matches_gapped_ground_truth(tmp_path):
    """A 20-minute sensor dropout must surface as a gap, not a shorter ride."""
    gap = (3000, 4199)  # inclusive window, 1,200 samples dropped
    db = Database(tmp_path / "garmin.db")
    seed_garmin_ride(db, gaps=[gap])
    result = QueryService(db, SYNTHETIC_USER_ID).get_workout_series(GARMIN_RIDE_WORKOUT_ID)

    truth_bpms = [
        bpm for t, bpm in enumerate(synthetic_ride_bpms()) if not (gap[0] <= t <= gap[1])
    ]
    assert len(truth_bpms) == 9_600
    assert_stats_match_truth(result["stats"], truth_bpms)

    quality = result["data_quality"]
    assert quality["actual_samples"] == 9_600
    assert quality["expected_samples"] == 10_800
    assert quality["coverage_ratio"] == pytest.approx(0.889, abs=0.001)
    # Samples resume at t=4200 after t=2999: a 1,201-second hole.
    assert quality["longest_gap_seconds"] == 1201

    # No downsampled bucket may come from inside the dropped window.
    offsets = [p["t"] for p in result["points"]]
    assert all(t < gap[0] or t >= gap[1] + 1 for t in offsets)


def test_garmin_layout_without_clock_column(tmp_path):
    """Without directTimestamp, row ordinals are the offsets (gap-free only)."""
    payload = build_garmin_ride(include_timestamp=False)
    samples = parse_garmin_heart_rate(payload)
    assert [offset for offset, _ in samples] == list(range(10_800))
    assert [bpm for _, bpm in samples] == synthetic_ride_bpms()

    db = Database(tmp_path / "garmin.db")
    seed_garmin_ride(db, include_timestamp=False)
    result = QueryService(db, SYNTHETIC_USER_ID).get_workout_series(GARMIN_RIDE_WORKOUT_ID)
    assert_stats_match_truth(result["stats"], synthetic_ride_bpms())
    assert result["data_quality"]["coverage_ratio"] == 1.0
    assert result["data_quality"]["sample_interval_seconds"] == 1.0


def test_ground_truth_percentile_helper_is_sound():
    """Sanity-check the independent percentile helper against statistics."""
    bpms = synthetic_ride_bpms()
    truth = ground_truth_stats(bpms)
    quartiles = statistics.quantiles(bpms, n=4, method="inclusive")
    assert truth["p25"] == pytest.approx(quartiles[0])
    assert truth["p50"] == pytest.approx(quartiles[1])
    assert truth["p75"] == pytest.approx(quartiles[2])
    assert truth["avg"] == pytest.approx(statistics.fmean(bpms))
