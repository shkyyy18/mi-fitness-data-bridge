from __future__ import annotations

import asyncio
import json
import sqlite3
from types import SimpleNamespace

from mi_fitness_mcp import main as cli
from mi_fitness_mcp.config import Config, load_config, resolve_database_path
from mi_fitness_mcp.storage import Database


def _seed_database(path, steps=8000):
    Database(path)
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            INSERT INTO daily_activity
              (id, provider, source_type, user_id, date, steps, distance_m, active_kcal)
            VALUES ('daily-1', 'xiaomi', 'cloud', 'synthetic-user', '2026-07-14', ?, 6000, 400)
            """,
            (steps,),
        )
    return path


def _export_steps(output) -> int:
    payload = json.loads(output.read_text(encoding="utf-8"))
    return payload["records"]["daily_activity"][0]["steps"]


def test_load_config_does_not_write_default_config(monkeypatch, tmp_path):
    config_path = tmp_path / "cfg" / "config.json"
    monkeypatch.setattr("mi_fitness_mcp.config.get_config_path", lambda: config_path)

    config = load_config()

    assert config.mode == "not_configured"
    assert not config_path.exists()


def test_resolve_database_path_precedence(monkeypatch, tmp_path):
    cli_path = tmp_path / "cli.db"
    env_path = tmp_path / "env.db"
    monkeypatch.setenv("MI_FITNESS_DB_PATH", str(env_path))

    assert resolve_database_path(cli_path) == cli_path
    assert resolve_database_path(None) == env_path

    monkeypatch.delenv("MI_FITNESS_DB_PATH")
    assert resolve_database_path(None) is None


def test_export_uses_cli_db_override(monkeypatch, tmp_path):
    database = _seed_database(tmp_path / "custom.db", steps=8000)
    monkeypatch.setattr(
        cli, "load_config", lambda: Config(database_path=tmp_path / "default.db")
    )
    monkeypatch.delenv("MI_FITNESS_DB_PATH", raising=False)
    output = tmp_path / "export.json"

    cli.cmd_export(
        SimpleNamespace(
            db=database, output=output, format="json", type=None,
            start_date=None, end_date=None,
        )
    )

    assert _export_steps(output) == 8000


def test_export_uses_env_db_override(monkeypatch, tmp_path):
    database = _seed_database(tmp_path / "env.db", steps=9000)
    monkeypatch.setattr(
        cli, "load_config", lambda: Config(database_path=tmp_path / "default.db")
    )
    monkeypatch.setenv("MI_FITNESS_DB_PATH", str(database))
    output = tmp_path / "export.json"

    cli.cmd_export(
        SimpleNamespace(
            db=None, output=output, format="json", type=None,
            start_date=None, end_date=None,
        )
    )

    assert _export_steps(output) == 9000


def test_export_cli_db_beats_env_db(monkeypatch, tmp_path):
    cli_db = _seed_database(tmp_path / "cli.db", steps=8000)
    env_db = _seed_database(tmp_path / "env.db", steps=9000)
    monkeypatch.setattr(
        cli, "load_config", lambda: Config(database_path=tmp_path / "default.db")
    )
    monkeypatch.setenv("MI_FITNESS_DB_PATH", str(env_db))
    output = tmp_path / "export.json"

    cli.cmd_export(
        SimpleNamespace(
            db=cli_db, output=output, format="json", type=None,
            start_date=None, end_date=None,
        )
    )

    assert _export_steps(output) == 8000


def test_sync_uses_cli_db_override(monkeypatch, tmp_path):
    captured: dict[str, object] = {}
    custom_db = tmp_path / "custom.db"

    class FakeDatabase:
        def __init__(self, path):
            captured["db_path"] = path

    class ConnectedAdapter:
        async def connect(self):
            return True

        def get_available_data_types(self):
            return ["daily_activity"]

        async def close(self):
            captured["closed"] = True

    class FakeSyncService:
        def __init__(self, adapter, db, default_lookback_days, chunk_days):
            pass

        async def sync_data_type(self, **kwargs):
            return {"status": "ok", "added": 0, "updated": 0, "skipped": 0}

    monkeypatch.setattr(
        cli,
        "load_config",
        lambda: Config(
            mode="mi_fitness_cloud", database_path=tmp_path / "default.db"
        ),
    )
    monkeypatch.setattr(
        cli, "load_mi_fitness_token", lambda: ("synthetic-user", "synthetic-token")
    )
    monkeypatch.setattr(cli, "_create_cloud_adapter", lambda *args: ConnectedAdapter())
    monkeypatch.setattr(cli, "SyncService", FakeSyncService)
    monkeypatch.setattr(cli, "Database", FakeDatabase)
    monkeypatch.delenv("MI_FITNESS_DB_PATH", raising=False)

    args = SimpleNamespace(db=custom_db, type=None, start_date=None, end_date=None)
    asyncio.run(cli.cmd_sync_async(args))

    assert captured["db_path"] == custom_db
    assert captured["closed"] is True


def test_sync_uses_env_db_override(monkeypatch, tmp_path):
    captured: dict[str, object] = {}
    env_db = tmp_path / "env.db"

    class FakeDatabase:
        def __init__(self, path):
            captured["db_path"] = path

    class ConnectedAdapter:
        async def connect(self):
            return True

        def get_available_data_types(self):
            return ["daily_activity"]

        async def close(self):
            pass

    class FakeSyncService:
        def __init__(self, adapter, db, default_lookback_days, chunk_days):
            pass

        async def sync_data_type(self, **kwargs):
            return {"status": "ok", "added": 0, "updated": 0, "skipped": 0}

    monkeypatch.setattr(
        cli,
        "load_config",
        lambda: Config(
            mode="mi_fitness_cloud", database_path=tmp_path / "default.db"
        ),
    )
    monkeypatch.setattr(
        cli, "load_mi_fitness_token", lambda: ("synthetic-user", "synthetic-token")
    )
    monkeypatch.setattr(cli, "_create_cloud_adapter", lambda *args: ConnectedAdapter())
    monkeypatch.setattr(cli, "SyncService", FakeSyncService)
    monkeypatch.setattr(cli, "Database", FakeDatabase)
    monkeypatch.setenv("MI_FITNESS_DB_PATH", str(env_db))

    args = SimpleNamespace(db=None, type=None, start_date=None, end_date=None)
    asyncio.run(cli.cmd_sync_async(args))

    assert captured["db_path"] == env_db
