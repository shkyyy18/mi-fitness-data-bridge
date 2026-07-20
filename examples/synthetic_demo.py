"""End-to-end synthetic demo: seed a local SQLite cache, then export JSON/CSV.

Uses only synthetic values. No credentials, network access, or personal data.
Run from the repository root after ``pip install -e .``:

    python examples/synthetic_demo.py
"""

from __future__ import annotations

import json
import tempfile
from datetime import datetime
from pathlib import Path

from mi_fitness_mcp.export import export_database
from mi_fitness_mcp.models import (
    BodyMeasurement,
    DailyActivity,
    SleepSession,
    SleepStage,
    Workout,
)
from mi_fitness_mcp.storage import Database

USER_ID = "synthetic-demo-user"


def seed(db: Database) -> None:
    base = {"provider": "mi_fitness", "source_type": "cloud_session", "user_id": USER_ID}
    db.insert_daily_activity(
        DailyActivity(
            id="demo-activity-1",
            date="2026-07-15",
            steps=8432,
            distance_m=6120.5,
            active_kcal=312.0,
            total_kcal=2210.0,
            floors=6,
            active_minutes=54,
            **base,
        )
    )
    db.insert_sleep_session(
        SleepSession(
            id="demo-sleep-1",
            sleep_id="demo-sleep-1",
            start_at=datetime(2026, 7, 14, 23, 20),
            end_at=datetime(2026, 7, 15, 7, 5),
            duration_minutes=465,
            time_asleep_minutes=441,
            time_awake_minutes=24,
            sleep_score=86,
            stages=[
                SleepStage(stage="deep", minutes=82),
                SleepStage(stage="light", minutes=271),
                SleepStage(stage="rem", minutes=88),
                SleepStage(stage="awake", minutes=24),
            ],
            **base,
        )
    )
    db.insert_workout(
        Workout(
            id="demo-workout-1",
            workout_id="demo-workout-1",
            activity_type="running",
            start_at=datetime(2026, 7, 15, 18, 30),
            end_at=datetime(2026, 7, 15, 19, 12),
            duration_minutes=42,
            distance_m=7200.0,
            calories_kcal=480.0,
            avg_heart_rate_bpm=148,
            max_heart_rate_bpm=171,
            **base,
        )
    )
    db.insert_body_measurement(
        BodyMeasurement(
            id="demo-body-1",
            timestamp=datetime(2026, 7, 15, 7, 20),
            weight_kg=72.4,
            bmi=23.1,
            body_fat_pct=18.7,
            muscle_mass_kg=55.3,
            water_pct=56.2,
            visceral_fat_score=8,
            basal_metabolism_kcal=1650,
            **base,
        )
    )


def main() -> None:
    workdir = Path(tempfile.mkdtemp(prefix="mi-fitness-demo-"))
    db_path = workdir / "mi_fitness.db"

    db = Database(db_path)
    seed(db)
    print(f"Seeded synthetic database: {db_path}")
    for row in db.get_data_coverage(USER_ID):
        print(
            f"  {row['data_type']}: {row['first_date']} .. {row['last_date']}"
            f" ({row['days_with_data']} day(s))"
        )

    json_out = workdir / "exports" / "mi_fitness.json"
    csv_out = workdir / "exports" / "csv"
    written = export_database(db_path, json_out, output_format="json")
    written += export_database(db_path, csv_out, output_format="csv")
    print("\nExport completed")
    for path in written:
        print(f"  {path.name}")

    payload = json.loads(json_out.read_text(encoding="utf-8"))
    print("\nJSON envelope:")
    print(f"  schema_version: {payload['schema_version']}")
    print(f"  source: {payload['source']}")
    for name, records in payload["records"].items():
        if records:
            print(f"  records.{name}: {len(records)} row(s)")

    sleep_row = payload["records"]["sleep"][0]
    print("\nSample sleep row (synthetic):")
    print(f"  start_at={sleep_row['start_at']} end_at={sleep_row['end_at']}")
    print(f"  duration_minutes={sleep_row['duration_minutes']} score={sleep_row['sleep_score']}")
    print(f"  stages={sleep_row['stages']}")


if __name__ == "__main__":
    main()
