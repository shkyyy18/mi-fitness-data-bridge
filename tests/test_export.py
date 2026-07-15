from __future__ import annotations

import csv
import json
import sqlite3

from mi_fitness_mcp.export import export_database
from mi_fitness_mcp.storage import Database


def _sample_database(tmp_path):
    path = tmp_path / "mi_fitness.db"
    Database(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO daily_activity
              (id, provider, source_type, user_id, date, steps, distance_m, active_kcal)
            VALUES ('daily-1', 'xiaomi', 'cloud', 'private-user', '2026-07-14', 8000, 6000, 400)
            """
        )
        connection.execute(
            """
            INSERT INTO body_measurements
              (id, provider, source_type, user_id, timestamp, weight_kg)
            VALUES ('body-1', 'xiaomi', 'cloud', 'private-user', '2026-07-14T08:00:00', 73.2)
            """
        )
    return path


def test_json_export_has_normalized_records_and_no_credentials(tmp_path):
    database = _sample_database(tmp_path)
    target = tmp_path / "export.json"

    written = export_database(database, target, output_format="json")

    assert written == [target]
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "1.0"
    assert payload["records"]["daily_activity"][0]["steps"] == 8000
    text = target.read_text(encoding="utf-8")
    assert "passToken" not in text


def test_csv_export_can_filter_dataset_and_date(tmp_path):
    database = _sample_database(tmp_path)
    output = tmp_path / "csv"

    written = export_database(
        database,
        output,
        output_format="csv",
        dataset="body_measurements",
        start_date="2026-07-14",
        end_date="2026-07-14",
    )

    assert written == [output / "body_measurements.csv"]
    with written[0].open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["weight_kg"] == "73.2"
