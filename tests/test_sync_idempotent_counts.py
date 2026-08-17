"""Idempotent re-sync counts: added vs updated (#9).

100% synthetic data. Re-running the same date range must report
added=0/updated=N instead of counting every upsert attempt as an insert.
"""

from __future__ import annotations

import asyncio
from datetime import datetime

import pytest

from mi_fitness_mcp.models import DailyActivity, Workout
from mi_fitness_mcp.services.sync_service import SyncService
from mi_fitness_mcp.storage import Database

SYNTHETIC_USER_ID = "synthetic-test-user"
BASE = {
    "provider": "mi_fitness",
    "source_type": "cloud_session",
    "user_id": SYNTHETIC_USER_ID,
}


def _synthetic_activities() -> list[DailyActivity]:
    return [
        DailyActivity(
            id=f"synthetic-activity-{day}",
            date=f"2026-07-0{day}",
            steps=5000 + day,
            distance_m=3000.0 + day,
            active_kcal=200.0 + day,
            **BASE,
        )
        for day in (1, 2, 3)
    ]


def _synthetic_workouts() -> list[Workout]:
    start = datetime(2026, 7, 1, 8, 0, 0)
    end = datetime(2026, 7, 1, 9, 0, 0)
    return [
        Workout(
            id=f"synthetic-workout-{i}",
            workout_id=f"synthetic-workout-{i}",
            activity_type="cycling",
            start_at=start,
            end_at=end,
            duration_minutes=60,
            **BASE,
        )
        for i in (1, 2)
    ]


class SyntheticAdapter:
    def __init__(self, data_type: str, records: list):
        self.data_type = data_type
        self.records = records

    def is_connected(self) -> bool:
        return True

    def iter_daily_activity(self, start_date, end_date):
        return iter(self.records)

    def iter_workouts(self, start_date, end_date):
        return iter(self.records)


@pytest.fixture()
def db(tmp_path):
    return Database(tmp_path / "sync_counts.db")


def test_resync_same_range_reports_updates_not_new_rows(db):
    activities = _synthetic_activities()
    service = SyncService(SyntheticAdapter("daily_activity", activities), db)

    first = asyncio.run(
        service.sync_data_type("daily_activity", start_date="2026-07-01", end_date="2026-07-03")
    )
    assert first["status"] == "ok"
    assert first["added"] == 3
    assert first["updated"] == 0

    second = asyncio.run(
        service.sync_data_type("daily_activity", start_date="2026-07-01", end_date="2026-07-03")
    )
    assert second["status"] == "ok"
    assert second["added"] == 0
    assert second["updated"] == 3

    rows = db.query_daily_activity(SYNTHETIC_USER_ID, "2026-07-01", "2026-07-03")
    assert len(rows) == 3


def test_resync_workouts_with_compound_conflict_key(db):
    service = SyncService(SyntheticAdapter("workouts", _synthetic_workouts()), db)

    first = asyncio.run(
        service.sync_data_type("workouts", start_date="2026-07-01", end_date="2026-07-01")
    )
    assert first["added"] == 2
    assert first["updated"] == 0

    second = asyncio.run(
        service.sync_data_type("workouts", start_date="2026-07-01", end_date="2026-07-01")
    )
    assert second["added"] == 0
    assert second["updated"] == 2

    rows = db.query_workouts(SYNTHETIC_USER_ID, "2026-07-01", "2026-07-01")
    assert len(rows) == 2


def test_mixed_new_and_existing_rows_are_counted_separately(db):
    service = SyncService(SyntheticAdapter("daily_activity", _synthetic_activities()[:2]), db)
    asyncio.run(
        service.sync_data_type("daily_activity", start_date="2026-07-01", end_date="2026-07-03")
    )

    service = SyncService(SyntheticAdapter("daily_activity", _synthetic_activities()), db)
    result = asyncio.run(
        service.sync_data_type("daily_activity", start_date="2026-07-01", end_date="2026-07-03")
    )
    assert result["added"] == 1
    assert result["updated"] == 2

    rows = db.query_daily_activity(SYNTHETIC_USER_ID, "2026-07-01", "2026-07-03")
    assert len(rows) == 3
