"""Synthetic multi-hour workout fixtures for tests.

100% generated data: a deterministic 3-hour indoor ride at 1 Hz heart rate
(10,800 points). Contains no real user data, credentials, or measurements.
The generator returns the exact bpm list so tests can compare downsampling
output against known ground-truth statistics.
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta

from mi_fitness_mcp.models import HeartRateSample, Workout
from mi_fitness_mcp.storage import Database

SYNTHETIC_USER_ID = "synthetic-test-user"
SYNTHETIC_RIDE_WORKOUT_ID = "synthetic-ride-3h"
SYNTHETIC_RIDE_START = datetime(2026, 7, 15, 8, 0, 0)
DEFAULT_DURATION_SECONDS = 3 * 3600  # 10,800 points at 1 Hz


def synthetic_ride_bpms(duration_seconds: int = DEFAULT_DURATION_SECONDS) -> list[int]:
    """Deterministic 1 Hz heart rate profile for a synthetic endurance ride.

    Phases: 15 min warm-up, steady state with slow undulation, 3x(5 min
    threshold / 5 min recovery) intervals, tempo, 10 min cool-down.
    """
    bpms = []
    for t in range(duration_seconds):
        if t < 900:  # warm-up ramp 95 -> 125
            bpm = 95 + 30 * t / 900
        elif t < 7200:  # steady state around 138
            bpm = 138 + 6 * math.sin(2 * math.pi * (t - 900) / 300)
        elif t < 9000:  # intervals: 5 min at ~168, 5 min at 130
            bpm = 168 + 2 * math.sin(2 * math.pi * t / 60) if (t - 7200) % 600 < 300 else 130
        elif t < 10200:  # tempo around 150
            bpm = 150 + 3 * math.sin(2 * math.pi * t / 120)
        else:  # cool-down ramp 145 -> 100
            bpm = 145 - 45 * (t - 10200) / 600
        bpms.append(round(bpm))
    return bpms


def seed_synthetic_ride(
    db: Database,
    user_id: str = SYNTHETIC_USER_ID,
    workout_id: str = SYNTHETIC_RIDE_WORKOUT_ID,
    duration_seconds: int = DEFAULT_DURATION_SECONDS,
) -> list[int]:
    """Seed a synthetic ride workout plus its 1 Hz heart rate samples.

    Returns the ground-truth bpm list for assertions.
    """
    bpms = synthetic_ride_bpms(duration_seconds)
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
            distance_m=duration_seconds * 8.5,  # ~30.6 km/h synthetic pace
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
                timestamp=start + timedelta(seconds=i),
                bpm=bpm,
                sample_type="workout",
                **base,
            )
            for i, bpm in enumerate(bpms)
        ]
    )
    return bpms
