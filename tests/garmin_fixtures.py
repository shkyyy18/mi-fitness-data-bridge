"""Garmin-layout counterpart of the synthetic 3-hour ride fixture.

Renders the exact same closed-form heart-rate profile as
tests/synthetic_fixtures.py (same ride, point for point) in the Garmin
Connect activity-details payload shape (``metricDescriptors`` /
``activityDetailMetrics``) used by davidmosiah/garmin-mcp, so the same
workout can regression-test the downsampling pipeline from both data
layouts. Agreed with garmin-mcp in issue #19 as a cross-format regression
fixture.

100% generated data: no real user data, credentials, or measurements.
Only the payload layout mirrors the Garmin format; all values come from
the shared synthetic profile.
"""

from __future__ import annotations

from datetime import timedelta

from mi_fitness_mcp.models import HeartRateSample, Workout
from mi_fitness_mcp.storage import Database
from tests.synthetic_fixtures import (
    DEFAULT_DURATION_SECONDS,
    SYNTHETIC_RIDE_START,
    SYNTHETIC_USER_ID,
    synthetic_ride_bpms,
)

GARMIN_RIDE_WORKOUT_ID = "garmin-layout-ride-3h"
GARMIN_RIDE_ACTIVITY_ID = 9_900_000_001
# Synthetic epoch; only relative offsets are ever read back from the payload.
GARMIN_RIDE_START_EPOCH_MS = 1_753_000_000_000


def build_garmin_ride(
    duration_seconds: int = DEFAULT_DURATION_SECONDS,
    gaps: list[tuple[int, int]] | None = None,
    include_timestamp: bool = True,
    include_gps: bool = False,
) -> dict:
    """Build a Garmin-format details payload for the synthetic ride.

    ``gaps`` is a list of inclusive ``[start_sec, end_sec]`` windows whose
    rows are dropped, simulating sensor dropouts. ``include_timestamp=False``
    omits the ``directTimestamp`` clock column. ``include_gps=True`` adds
    lat/lon columns to prove descriptor-driven parsing ignores extra metrics.
    """
    gaps = gaps or []
    descriptors = []
    index = 0
    if include_timestamp:
        descriptors.append(
            {"key": "directTimestamp", "metricsIndex": index, "unit": {"key": "gmt"}}
        )
        index += 1
    descriptors.append({"key": "directHeartRate", "metricsIndex": index, "unit": {"key": "bpm"}})
    index += 1
    descriptors.append({"key": "directPower", "metricsIndex": index, "unit": {"key": "watt"}})
    index += 1
    if include_gps:
        descriptors.append(
            {"key": "directLatitude", "metricsIndex": index, "unit": {"key": "degree"}}
        )
        index += 1
        descriptors.append(
            {"key": "directLongitude", "metricsIndex": index, "unit": {"key": "degree"}}
        )
        index += 1

    bpms = synthetic_ride_bpms(duration_seconds)
    rows = []
    for t, bpm in enumerate(bpms):
        if any(start <= t <= end for start, end in gaps):
            continue
        metrics = []
        if include_timestamp:
            metrics.append(GARMIN_RIDE_START_EPOCH_MS + t * 1000)
        metrics.append(bpm)
        metrics.append(max(0, round((bpm - 60) * 2.4)))  # synthetic power, tracks HR
        if include_gps:
            metrics.append(-3.7327 + t * 0.000001)
            metrics.append(-38.5267 + t * 0.000001)
        rows.append({"metrics": metrics})

    return {
        "activityId": GARMIN_RIDE_ACTIVITY_ID,
        "measurementCount": len(rows),
        "metricsCount": len(descriptors),
        "metricDescriptors": descriptors,
        "activityDetailMetrics": rows,
    }


def parse_garmin_heart_rate(payload: dict) -> list[tuple[int, int]]:
    """Extract ``(offset_seconds_from_start, bpm)`` pairs from a Garmin payload.

    Column positions are resolved through ``metricDescriptors`` by key, never
    by fixed index, so extra metrics (power, GPS) are ignored. When the
    ``directTimestamp`` clock column is absent, the row ordinal is used as the
    second offset (correct only for gap-free payloads).
    """
    indexes = {d["key"]: d["metricsIndex"] for d in payload["metricDescriptors"]}
    hr_index = indexes["directHeartRate"]
    ts_index = indexes.get("directTimestamp")

    samples: list[tuple[int, int]] = []
    first_ts: float | None = None
    for ordinal, row in enumerate(payload["activityDetailMetrics"]):
        metrics = row["metrics"]
        bpm = int(round(metrics[hr_index]))
        if ts_index is None:
            offset = ordinal
        else:
            ts = metrics[ts_index]
            if first_ts is None:
                first_ts = ts
            offset = round((ts - first_ts) / 1000)
        samples.append((offset, bpm))
    return samples


def seed_garmin_ride(
    db: Database,
    user_id: str = SYNTHETIC_USER_ID,
    workout_id: str = GARMIN_RIDE_WORKOUT_ID,
    duration_seconds: int = DEFAULT_DURATION_SECONDS,
    gaps: list[tuple[int, int]] | None = None,
    include_timestamp: bool = True,
    include_gps: bool = False,
) -> list[tuple[int, int]]:
    """Build the Garmin-layout payload, parse it, and seed it as a workout.

    Returns the parsed ``(offset_seconds, bpm)`` series; tests compute ground
    truth independently from ``synthetic_ride_bpms`` instead of trusting this.
    """
    payload = build_garmin_ride(
        duration_seconds=duration_seconds,
        gaps=gaps,
        include_timestamp=include_timestamp,
        include_gps=include_gps,
    )
    samples = parse_garmin_heart_rate(payload)
    bpms = [bpm for _, bpm in samples]
    # The storage layer only accepts provider="mi_fitness"; the Garmin-ness of
    # this fixture lives in the payload layout, not in the row label.
    base = {"provider": "mi_fitness", "source_type": "cloud_session", "user_id": user_id}
    start = SYNTHETIC_RIDE_START
    end = start + timedelta(seconds=duration_seconds)

    db.insert_workout(
        Workout(
            id=workout_id,
            workout_id=workout_id,
            activity_type="cycling",
            start_at=start,
            end_at=end,
            duration_minutes=duration_seconds // 60,
            distance_m=duration_seconds * 8.5,
            calories_kcal=duration_seconds * 0.2,
            avg_heart_rate_bpm=round(sum(bpms) / len(bpms)),
            max_heart_rate_bpm=max(bpms),
            **base,
        )
    )
    db.insert_heart_rate_samples(
        [
            HeartRateSample(
                id=f"{workout_id}-hr-{i}",
                timestamp=start + timedelta(seconds=offset),
                bpm=bpm,
                sample_type="workout",
                **base,
            )
            for i, (offset, bpm) in enumerate(samples)
        ]
    )
    return samples
