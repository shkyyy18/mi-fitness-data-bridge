# AGENTS.md

Read `PROJECT_GUIDE.md` and `README.md` before work.

- Use `D:\AIWorkspace\projects\mi_fitness_data_bridge` as the stable path.
- Keep credentials, databases, exports, logs, caches, and personal health data out of Git.
- Do not duplicate this connector inside downstream projects.
- Preserve the experimental/unofficial status and upstream MIT attribution.
- Run `python -m pytest -q -p no:cacheprovider` after changes.

## Text encoding

- Pure Python project: pass `encoding="utf-8"` on every text file read/write and explicit `encoding` on `subprocess` text capture; user health data may contain Chinese.
- Export convention: JSON is UTF-8, CSV is `utf-8-sig` (BOM, so Excel opens Chinese correctly); SQLite stores text natively.
