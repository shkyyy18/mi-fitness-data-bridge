"""Portable exports for the normalized Mi Fitness SQLite cache."""

from __future__ import annotations

import csv
import json
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

DATASETS: dict[str, tuple[str, str]] = {
    "daily_activity": ("daily_activity", "date"),
    "sleep": ("sleep_sessions", "start_at"),
    "workouts": ("workouts", "start_at"),
    "body_measurements": ("body_measurements", "timestamp"),
    "heart_rate": ("heart_rate_samples", "timestamp"),
    "spo2": ("spo2_samples", "timestamp"),
    "stress": ("stress_samples", "timestamp"),
    "abnormal_heart_beat": ("abnormal_heart_beat_events", "start_at"),
}


class ExportResult(list[Path]):
    """Written export paths plus per-dataset row counts."""

    def __init__(self, paths: list[Path], row_counts: dict[str, int]) -> None:
        super().__init__(paths)
        self.row_counts = row_counts


def _validate_date_range(start_date: str | None, end_date: str | None) -> None:
    parsed: dict[str, date] = {}
    for name, value in (("start_date", start_date), ("end_date", end_date)):
        if value is None:
            continue
        try:
            parsed_value = date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{name} must use YYYY-MM-DD format") from exc
        if parsed_value.isoformat() != value:
            raise ValueError(f"{name} must use YYYY-MM-DD format")
        parsed[name] = parsed_value

    if (
        parsed.get("start_date")
        and parsed.get("end_date")
        and parsed["start_date"] > parsed["end_date"]
    ):
        raise ValueError("start_date must not be after end_date")


def _connect_read_only(database_path: Path) -> sqlite3.Connection:
    path = database_path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(f"Mi Fitness database does not exist: {path}")
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    return connection


def _rows(
    connection: sqlite3.Connection,
    dataset: str,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> tuple[list[str], list[dict[str, Any]]]:
    try:
        table, date_column = DATASETS[dataset]
    except KeyError as exc:
        raise ValueError(f"Unsupported dataset: {dataset}") from exc

    columns = [row[1] for row in connection.execute(f"PRAGMA table_info({table})")]
    clauses: list[str] = []
    values: list[str] = []
    if start_date:
        clauses.append(f"date({date_column}) >= date(?)")
        values.append(start_date)
    if end_date:
        clauses.append(f"date({date_column}) <= date(?)")
        values.append(end_date)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
    result = connection.execute(
        f"SELECT * FROM {table}{where} ORDER BY {date_column}", values
    ).fetchall()
    return columns, [dict(row) for row in result]


def export_database(
    database_path: Path | str,
    output_path: Path | str,
    *,
    output_format: str = "json",
    dataset: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> ExportResult:
    """Export normalized health records without credentials.

    JSON writes one envelope file. CSV writes one file per selected dataset.
    """

    if output_format not in {"json", "csv"}:
        raise ValueError("output_format must be 'json' or 'csv'")
    if dataset is not None and dataset not in DATASETS:
        raise ValueError(f"Unsupported dataset: {dataset}")
    _validate_date_range(start_date, end_date)

    database = Path(database_path)
    output = Path(output_path).expanduser()
    selected = [dataset] if dataset else list(DATASETS)
    written: list[Path] = []

    with _connect_read_only(database) as connection:
        records: dict[str, list[dict[str, Any]]] = {}
        columns: dict[str, list[str]] = {}
        for name in selected:
            columns[name], records[name] = _rows(
                connection, name, start_date=start_date, end_date=end_date
            )
        row_counts = {name: len(records[name]) for name in selected}

    if output_format == "json":
        target = output if output.suffix.lower() == ".json" else output / "mi_fitness_export.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "schema_version": "1.0",
            "source": "mi_fitness_data_bridge",
            "generated_at": datetime.now(UTC).isoformat(),
            "filters": {
                "dataset": dataset,
                "start_date": start_date,
                "end_date": end_date,
            },
            "records": records,
        }
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        written.append(target)
        return ExportResult(written, row_counts)

    output.mkdir(parents=True, exist_ok=True)
    for name in selected:
        target = output / f"{name}.csv"
        with target.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=columns[name])
            writer.writeheader()
            writer.writerows(records[name])
        written.append(target)
    return ExportResult(written, row_counts)
