# Release checklist

## Local validation

- [x] Tests and Ruff pass on supported Python versions.
- [x] Python syntax checks and `git diff --check` pass.
- [x] Wheel builds and installs in an isolated target.
- [x] Both console commands are present in wheel metadata.
- [x] No credential, database, export, log, personal identifier, or real health value is tracked.
- [x] Release screenshots contain synthetic values only.

## GitHub publication

- [x] Create `shkyyy18/mi-fitness-data-bridge` as a public repository.
- [x] Push `main` and the annotated `v0.2.0` tag.
- [x] Confirm CI passes for Python 3.11, 3.12, and 3.13.
- [ ] Enable private vulnerability reporting.
- [ ] Configure branch protection or a ruleset after the first push.
- [ ] Publish release notes from `CHANGELOG.md`.

## Post-release observation

- [ ] Record installation and successful-sync reports without default telemetry.
- [ ] Track device/region compatibility Issues.
- [ ] Track external Issues, pull requests, contributors, and downstream integrations.
- [ ] Keep all connector fixes in this repository rather than copying them downstream.

## Validation evidence

- 2026-07-16: 17 tests, Ruff, Python syntax compilation, and `git diff --check` passed.
- 2026-07-16: a fresh wheel was built and installed into an isolated target; wheel metadata contains both `mi-fitness-bridge` and `mi-fitness-mcp`.
- 2026-07-16: tracked-file scanning found no credential, database, export, log, personal identifier, health-data, or screenshot artifacts. With no tracked screenshots, the synthetic-screenshot requirement is currently satisfied by absence.
- 2026-07-16: the public repository, synchronized `main`, annotated `v0.2.0` tag, and successful Python 3.11/3.12/3.13 CI were verified.
- Still open: vulnerability reporting, branch rules, GitHub Release notes, and post-release adoption evidence.
