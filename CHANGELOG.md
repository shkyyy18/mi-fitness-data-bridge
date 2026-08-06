# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Added

- Agent-safe `workout_series` MCP tool: auto-downsamples workout time series under a hard `max_points` cap (default 400, max 500) using fixed time-bucket means aggregated in SQLite, reports honest `downsampled`/`source_points`/`returned_points`/`method` metadata, and always includes full-resolution stats (avg/min/max/quantiles) and heart-rate time-in-zone.
- `data_quality` field (coverage days, missing metrics, last sync time) on `query_workouts` and `get_daily_summary` responses.
- Synthetic 3-hour ride fixture (10,800 1 Hz heart-rate points with known ground-truth stats) and regression tests for the downsampling pipeline.
- `workout_series` contract `agent-safe-series/v1`: top-level `start_time`, `t_unit` (`seconds_from_start`), `unit`, `contract_version`, and `requested_resolution_seconds` (alongside the effective `resolution_seconds`); `stats.percentile_method` (`linear_interpolation`); `time_in_zone.reference_source` (`activity_recorded_max` / `observed_max` / `caller_provided`); `data_quality.actual_samples`, `data_quality.sample_interval_seconds`, and `data_quality.coverage_anchor`.
- Optional `reference_max_hr` input on `workout_series` so agents can normalize time-in-zone against a consistent reference when comparing activities.
- Duration-anchored coverage in `workout_series`: `expected_samples` is computed from the activity's nominal duration (workout `duration_minutes`, else the recorded start/end), so samples missing at the start or end of an activity surface as `coverage_ratio < 1.0` instead of looking like a shorter, fully-sampled workout; falls back to the first-to-last sample span (`coverage_anchor: "sample_span"`) when no nominal duration is recorded.
- Garmin-layout counterpart of the synthetic 3-hour ride fixture (`tests/garmin_fixtures.py`, `metricDescriptors`/`activityDetailMetrics` shape) plus cross-format regression tests proving both layouts yield identical stats and downsampled points, including a sensor-gap scenario (garmin-mcp issue #19).

### Changed

- **Breaking:** `workout_series` `points[].t` is now a numeric offset in seconds from `start_time` instead of an ISO timestamp string.

- Hide passToken entry in the interactive setup flow.
- Close the experimental cloud adapter reliably after CLI diagnostics and synchronization.
- Use `cn` consistently as the default cloud region.
- Reject malformed or reversed export date ranges before reading the local database.
- Apply configured HTTP limits, retries, pagination, sync chunking, and operation timeouts to CLI diagnostics and synchronization.
- Reject invalid synchronization lookback and chunk sizes instead of risking non-terminating chunk loops.
- Report partial and failed CLI synchronization results accurately instead of displaying them as successful.
- Return a non-zero process status when diagnostics are not ready or any synchronization is partial/failed.

## [0.2.0] - 2026-07-15

### Added

- Independent `mi-fitness-data-bridge` package and repository boundary.
- SQLite, JSON, CSV, Python, and MCP-compatible access paths.
- Dataset/date-filtered `export` command.
- `mi-fitness-bridge` command with the `mi-fitness-mcp` compatibility alias.
- Local keyring setup and diagnostic commands.
- Security, contribution, CI, and third-party attribution documentation.
- Synthetic release screenshot with no credentials or personal health data.

### Changed

- Preserved the `mi_fitness_mcp` Python namespace for downstream compatibility.
- Clarified that the Xiaomi cloud adapter is unofficial and experimental.

[0.2.0]: https://github.com/shkyyy18/mi-fitness-data-bridge/releases/tag/v0.2.0
