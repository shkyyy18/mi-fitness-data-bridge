# Release checklist

## Local validation

- [ ] Tests and Ruff pass on supported Python versions.
- [ ] Python syntax checks and `git diff --check` pass.
- [ ] Wheel builds and installs in an isolated target.
- [ ] Both console commands are present in wheel metadata.
- [ ] No credential, database, export, log, personal identifier, or real health value is tracked.
- [ ] Release screenshots contain synthetic values only.

## GitHub publication

- [ ] Create `shkyyy18/mi-fitness-data-bridge` as a public repository.
- [ ] Push `main` and the annotated `v0.2.0` tag.
- [ ] Confirm CI passes for Python 3.11, 3.12, and 3.13.
- [ ] Enable private vulnerability reporting.
- [ ] Configure branch protection or a ruleset after the first push.
- [ ] Publish release notes from `CHANGELOG.md`.

## Post-release observation

- [ ] Record installation and successful-sync reports without default telemetry.
- [ ] Track device/region compatibility Issues.
- [ ] Track external Issues, pull requests, contributors, and downstream integrations.
- [ ] Keep all connector fixes in this repository rather than copying them downstream.
