# Changelog

All notable changes to this project will be documented in this file.

## [Unreleased]

### Changed

- Hide passToken entry in the interactive setup flow.
- Close the experimental cloud adapter reliably after CLI diagnostics and synchronization.
- Use `cn` consistently as the default cloud region.
- Reject malformed or reversed export date ranges before reading the local database.
- Apply configured HTTP limits, retries, pagination, sync chunking, and operation timeouts to CLI diagnostics and synchronization.
- Reject invalid synchronization lookback and chunk sizes instead of risking non-terminating chunk loops.
- Report partial and failed CLI synchronization results accurately instead of displaying them as successful.

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
