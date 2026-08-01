"""Query service for retrieving data from database."""

import math
import statistics
from contextlib import suppress
from datetime import datetime, timedelta
from itertools import pairwise
from typing import Any

from mi_fitness_mcp.storage import Database

# Heart rate zones as fractions of a reference max heart rate (upper bound excluded).
ZONE_FRACTIONS = (0.6, 0.7, 0.8, 0.9)

# Agent-safety limits for workout_series: responses must stay small enough for LLM context.
DEFAULT_RESOLUTION_SECONDS = 60
DEFAULT_MAX_POINTS = 400
HARD_MAX_POINTS = 500


class QueryService:
    """Service for querying fitness data from local database."""

    def __init__(self, db: Database, user_id: str):
        """Initialize query service.

        Args:
            db: Database instance
            user_id: User identifier
        """
        self.db = db
        self.user_id = user_id

    def get_daily_summaries(self, start_date: str, end_date: str) -> list[dict[str, Any]]:
        """Get daily activity summaries for date range."""
        records = self.db.query_daily_activity(self.user_id, start_date, end_date)

        # 按日期分组并聚合
        summaries = {}
        for record in records:
            date = record["date"]
            if date not in summaries:
                summaries[date] = {
                    "date": date,
                    "steps": 0,
                    "distance_m": 0,
                    "active_kcal": 0,
                    "total_kcal": 0,
                    "floors": 0,
                    "active_minutes": 0,
                }

            summaries[date]["steps"] += record.get("steps", 0)
            summaries[date]["distance_m"] += record.get("distance_m", 0)
            summaries[date]["active_kcal"] += record.get("active_kcal", 0)
            if record.get("total_kcal"):
                summaries[date]["total_kcal"] += record["total_kcal"]
            if record.get("floors"):
                summaries[date]["floors"] += record["floors"]
            if record.get("active_minutes"):
                summaries[date]["active_minutes"] += record["active_minutes"]

        return list(summaries.values())

    def get_metric_series(
        self,
        metric: str,
        start_date: str,
        end_date: str,
        granularity: str = "day",
        aggregation: str = "sum",
    ) -> list[dict[str, Any]]:
        """Get time series for a metric."""
        summaries = self.get_daily_summaries(start_date, end_date)

        series = []
        for summary in summaries:
            value = summary.get(metric)
            if value is not None:
                series.append(
                    {
                        "date": summary["date"],
                        "value": value,
                    }
                )

        # 按需执行周/月聚合
        if granularity == "week":
            series = self._aggregate_by_week(series, aggregation)
        elif granularity == "month":
            series = self._aggregate_by_month(series, aggregation)

        return series

    def _aggregate_by_week(
        self,
        series: list[dict],
        aggregation: str,
    ) -> list[dict]:
        """Aggregate daily series by week."""
        weeks = {}

        for item in series:
            date = datetime.strptime(item["date"], "%Y-%m-%d")
            # 计算周起始日（周一）
            week_start = date - timedelta(days=date.weekday())
            week_key = week_start.strftime("%Y-%m-%d")

            if week_key not in weeks:
                weeks[week_key] = []
            weeks[week_key].append(item["value"])

        result = []
        for week_key, values in sorted(weeks.items()):
            if aggregation == "sum":
                value = sum(values)
            elif aggregation == "avg":
                value = sum(values) / len(values)
            elif aggregation == "min":
                value = min(values)
            elif aggregation == "max":
                value = max(values)
            else:
                value = sum(values)

            result.append({"date": week_key, "value": value})

        return result

    def _aggregate_by_month(
        self,
        series: list[dict],
        aggregation: str,
    ) -> list[dict]:
        """Aggregate daily series by month."""
        months = {}

        for item in series:
            date = datetime.strptime(item["date"], "%Y-%m-%d")
            month_key = date.strftime("%Y-%m")

            if month_key not in months:
                months[month_key] = []
            months[month_key].append(item["value"])

        result = []
        for month_key, values in sorted(months.items()):
            if aggregation == "sum":
                value = sum(values)
            elif aggregation == "avg":
                value = sum(values) / len(values)
            elif aggregation == "min":
                value = min(values)
            elif aggregation == "max":
                value = max(values)
            else:
                value = sum(values)

            result.append({"date": month_key + "-01", "value": value})

        return result

    def get_sleep_sessions(
        self,
        start_date: str,
        end_date: str,
        include_naps: bool = True,
    ) -> list[dict[str, Any]]:
        """Get sleep sessions for date range."""
        records = self.db.query_sleep_sessions(self.user_id, start_date, end_date)

        sessions = []
        for record in records:
            # 不包含小睡时跳过 nap 记录
            if not include_naps and record.get("is_nap"):
                continue

            session = {
                "sleep_id": record["sleep_id"],
                "start_at": record["start_at"],
                "end_at": record["end_at"],
                "duration_minutes": record["duration_minutes"],
                "time_asleep_minutes": record["time_asleep_minutes"],
                "time_awake_minutes": record["time_awake_minutes"],
                "sleep_score": record.get("sleep_score"),
                "is_nap": record.get("is_nap", False),
            }

            # 如有睡眠阶段信息则解析
            if record.get("stages"):
                import json

                with suppress(json.JSONDecodeError):
                    session["stages"] = json.loads(record["stages"])

            sessions.append(session)

        return sessions

    def get_workouts(
        self,
        start_date: str,
        end_date: str,
        activity_types: list[str] | None = None,
        min_duration: int | None = None,
        min_distance_km: float | None = None,
    ) -> list[dict[str, Any]]:
        """Get workouts for date range with optional filters."""
        records = self.db.query_workouts(self.user_id, start_date, end_date)

        workouts = []
        for record in records:
            # 应用过滤条件
            if activity_types and record["activity_type"].lower() not in [
                t.lower() for t in activity_types
            ]:
                continue

            if min_duration and record.get("duration_minutes", 0) < min_duration:
                continue

            if min_distance_km:
                distance_km = (record.get("distance_m") or 0) / 1000
                if distance_km < min_distance_km:
                    continue

            workouts.append(
                {
                    "workout_id": record["workout_id"],
                    "activity_type": record["activity_type"],
                    "start_at": record["start_at"],
                    "end_at": record["end_at"],
                    "duration_minutes": record["duration_minutes"],
                    "distance_m": record.get("distance_m"),
                    "calories_kcal": record.get("calories_kcal"),
                    "avg_heart_rate_bpm": record.get("avg_heart_rate_bpm"),
                    "max_heart_rate_bpm": record.get("max_heart_rate_bpm"),
                    "avg_pace_sec_per_km": record.get("avg_pace_sec_per_km"),
                    "max_pace_sec_per_km": record.get("max_pace_sec_per_km"),
                    "total_steps": record.get("total_steps"),
                }
            )

        return workouts

    def get_workout_series(
        self,
        workout_id: str,
        metric: str = "heart_rate",
        resolution: int = DEFAULT_RESOLUTION_SECONDS,
        max_points: int = DEFAULT_MAX_POINTS,
    ) -> dict[str, Any]:
        """Get an agent-safe time series for one workout metric.

        The full-resolution series is never returned raw when it exceeds
        ``max_points``; instead it is downsampled into fixed time buckets whose
        mean (plus per-bucket min/max) is computed in SQLite. The payload always
        states whether downsampling happened, which method was used, and how
        many source points it represents, so agents never mistake a downsampled
        series for full precision. Summary statistics and time-in-zone are
        always computed on the full-resolution samples.

        Raises:
            ValueError: if the metric is unsupported or the workout is unknown
        """
        if metric != "heart_rate":
            raise ValueError(f"Unsupported workout metric: {metric}")
        if resolution < 1:
            raise ValueError("resolution must be at least 1 second")
        max_points = max(1, min(int(max_points), HARD_MAX_POINTS))

        workout = self.db.get_workout(self.user_id, workout_id)
        if workout is None:
            raise ValueError(f"Unknown workout_id: {workout_id}")

        start_at = workout["start_at"]
        end_at = workout["end_at"]

        # Prefer explicit workout samples; fall back to every sample in the window.
        samples = self.db.query_heart_rate_samples_range(
            self.user_id, start_at, end_at, sample_type="workout"
        )
        sample_type = "workout"
        if not samples:
            samples = self.db.query_heart_rate_samples_range(self.user_id, start_at, end_at)
            sample_type = "any"

        bpms = [int(s["bpm"]) for s in samples]
        source_points = len(bpms)

        start_dt = datetime.fromisoformat(start_at)
        end_dt = datetime.fromisoformat(end_at)
        duration_seconds = max(1, int((end_dt - start_dt).total_seconds()))

        if source_points == 0:
            return {
                "workout_id": workout_id,
                "activity_type": workout["activity_type"],
                "metric": metric,
                "unit": "bpm",
                "start_at": start_at,
                "end_at": end_at,
                "duration_seconds": duration_seconds,
                "resolution_seconds": resolution,
                "points": [],
                "stats": None,
                "time_in_zone": None,
                "downsampled": False,
                "source_points": 0,
                "returned_points": 0,
                "method": "none",
                "data_quality": {
                    "sample_type": sample_type,
                    "expected_samples": 0,
                    "coverage_ratio": 0.0,
                    "longest_gap_seconds": duration_seconds,
                    "missing_metrics": [metric],
                },
            }

        timestamps = [datetime.fromisoformat(s["timestamp"]) for s in samples]
        gaps = [(b - a).total_seconds() for a, b in pairwise(timestamps)]
        median_interval = statistics.median(gaps) if gaps else 1.0
        longest_gap = max(gaps) if gaps else 0.0

        downsampled = source_points > max_points
        if downsampled:
            # Adaptive bucket size: honor the requested resolution unless it would
            # produce more points than the caller allows.
            bucket_seconds = max(resolution, math.ceil(duration_seconds / max_points))
            buckets = self.db.query_heart_rate_buckets(
                self.user_id,
                start_at,
                end_at,
                bucket_seconds,
                sample_type="workout" if sample_type == "workout" else None,
            )
            points = [
                {
                    "t": str(b["bucket_start"]).replace(" ", "T"),
                    "value": round(b["avg_bpm"], 1),
                    "min": b["min_bpm"],
                    "max": b["max_bpm"],
                    "samples": b["sample_count"],
                }
                for b in buckets
            ]
            method = "time_bucket_mean"
        else:
            bucket_seconds = resolution
            points = [
                {"t": s["timestamp"], "value": int(s["bpm"])}
                for s in samples
            ]
            method = "none"

        quartiles = statistics.quantiles(bpms, n=4, method="inclusive")
        stats = {
            "avg": round(statistics.fmean(bpms), 1),
            "min": min(bpms),
            "max": max(bpms),
            "p25": round(quartiles[0], 1),
            "p50": round(quartiles[1], 1),
            "p75": round(quartiles[2], 1),
        }

        reference_max = workout.get("max_heart_rate_bpm") or max(bpms)
        bounds = [int(reference_max * f) for f in ZONE_FRACTIONS]
        zone_seconds = [0.0] * (len(bounds) + 1)
        for bpm in bpms:
            zone = sum(bpm >= bound for bound in bounds)
            zone_seconds[zone] += median_interval
        time_in_zone = {
            "zone_model": "percent_of_reference_max_hr",
            "reference_max_bpm": reference_max,
            "zones": [
                {
                    "zone": i + 1,
                    "min_bpm": bounds[i - 1] if i > 0 else None,
                    "max_bpm": bounds[i] - 1 if i < len(bounds) else None,
                    "seconds": round(zone_seconds[i]),
                }
                for i in range(len(bounds) + 1)
            ],
        }

        expected_samples = duration_seconds / median_interval if median_interval else 0
        return {
            "workout_id": workout_id,
            "activity_type": workout["activity_type"],
            "metric": metric,
            "unit": "bpm",
            "start_at": start_at,
            "end_at": end_at,
            "duration_seconds": duration_seconds,
            "resolution_seconds": bucket_seconds,
            "points": points,
            "stats": stats,
            "time_in_zone": time_in_zone,
            "downsampled": downsampled,
            "source_points": source_points,
            "returned_points": len(points),
            "method": method,
            "data_quality": {
                "sample_type": sample_type,
                "expected_samples": round(expected_samples),
                "coverage_ratio": round(min(1.0, source_points / expected_samples), 3)
                if expected_samples
                else 0.0,
                "longest_gap_seconds": round(longest_gap),
                "missing_metrics": [],
            },
        }

    def get_data_quality(
        self,
        data_type: str,
        missing_metrics: list[str] | None = None,
    ) -> dict[str, Any]:
        """Summarize local data quality for a data type.

        Combines coverage days, the last sync timestamp, and metrics that are
        absent from the cached records so agents can judge how much to trust
        summary/list responses.
        """
        coverage = next(
            (c for c in self.db.get_data_coverage(self.user_id) if c["data_type"] == data_type),
            None,
        )
        sync_state = self.db.get_sync_state(data_type)
        return {
            "data_type": data_type,
            "first_date": coverage["first_date"] if coverage else None,
            "last_date": coverage["last_date"] if coverage else None,
            "days_with_data": coverage["days_with_data"] if coverage else 0,
            "last_sync_at": sync_state.get("last_sync_at") if sync_state else None,
            "missing_metrics": missing_metrics or [],
        }

    def get_body_measurements(
        self,
        start_date: str,
        end_date: str,
        metrics: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Get body measurements for date range."""
        records = self.db.query_body_measurements(self.user_id, start_date, end_date)

        measurements = []
        for record in records:
            measurement = {
                "timestamp": record["timestamp"],
                "weight_kg": record["weight_kg"],
            }

            # 添加可选指标
            optional_fields = [
                "bmi",
                "body_fat_pct",
                "muscle_mass_kg",
                "water_pct",
                "bone_mass_kg",
                "visceral_fat_score",
                "basal_metabolism_kcal",
                "metabolic_age",
            ]

            for field in optional_fields:
                if record.get(field) is not None:
                    measurement[field] = record[field]

            # 如指定指标列表则过滤字段
            if metrics:
                filtered = {"timestamp": measurement["timestamp"]}
                for metric in metrics:
                    if metric in measurement:
                        filtered[metric] = measurement[metric]
                measurement = filtered

            measurements.append(measurement)

        return measurements

    def get_heart_rate_samples(
        self,
        start_date: str,
        end_date: str,
        sample_type: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        records = self.db.query_heart_rate_samples(self.user_id, start_date, end_date)

        samples = []
        for record in records:
            if sample_type and record.get("sample_type") != sample_type:
                continue
            samples.append(
                {
                    "timestamp": record["timestamp"],
                    "bpm": record["bpm"],
                    "sample_type": record.get("sample_type", "passive"),
                }
            )

        if limit is not None:
            return samples[:limit]
        return samples

    def get_spo2_samples(
        self,
        start_date: str,
        end_date: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        records = self.db.query_spo2_samples(self.user_id, start_date, end_date)
        samples = [
            {
                "timestamp": record["timestamp"],
                "spo2_pct": record["spo2_pct"],
            }
            for record in records
        ]
        return samples[:limit] if limit is not None else samples

    def get_stress_samples(
        self,
        start_date: str,
        end_date: str,
        level: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        records = self.db.query_stress_samples(self.user_id, start_date, end_date)
        samples = []
        for record in records:
            if level and record.get("level") != level:
                continue
            samples.append(
                {
                    "timestamp": record["timestamp"],
                    "stress_score": record["stress_score"],
                    "level": record["level"],
                }
            )
        return samples[:limit] if limit is not None else samples

    def get_abnormal_heart_beat_events(
        self,
        start_date: str,
        end_date: str,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        records = self.db.query_abnormal_heart_beat_events(self.user_id, start_date, end_date)
        events = [
            {
                "event_id": record["event_id"],
                "start_at": record["start_at"],
                "end_at": record["end_at"],
                "duration_seconds": record["duration_seconds"],
            }
            for record in records
        ]
        return events[:limit] if limit is not None else events

    def get_data_coverage(self, data_types: list[str] | None = None) -> list[dict[str, Any]]:
        """Get data coverage information."""
        coverage = self.db.get_data_coverage(self.user_id)

        if data_types:
            coverage = [c for c in coverage if c["data_type"] in data_types]

        return coverage
