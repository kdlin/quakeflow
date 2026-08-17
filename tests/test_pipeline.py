from __future__ import annotations

import shutil
import time
from pathlib import Path

import duckdb
import pytest

from quakeflow.config import ProjectPaths
from quakeflow.pipeline import run_pipeline


def source_payload() -> dict:
    now_ms = int(time.time() * 1000)
    return {
        "type": "FeatureCollection",
        "metadata": {"generated": now_ms, "count": 2},
        "features": [
            {
                "type": "Feature",
                "id": "test-1",
                "properties": {
                    "mag": 4.7,
                    "place": "5 km S of Example, Alaska",
                    "time": now_ms - 60_000,
                    "updated": now_ms,
                    "type": "earthquake",
                    "tsunami": 0,
                    "felt": 7,
                    "sig": 350,
                    "url": "https://example.com/test-1",
                    "net": "test",
                    "status": "reviewed",
                },
                "geometry": {"type": "Point", "coordinates": [-149.9, 61.2, 24.0]},
            },
            {
                "type": "Feature",
                "id": "bad-record",
                "properties": {"mag": "large"},
                "geometry": {"type": "Point", "coordinates": []},
            },
        ],
    }


def temporary_project(tmp_path: Path) -> ProjectPaths:
    source_sql = Path(__file__).resolve().parents[1] / "sql"
    target_sql = tmp_path / "sql"
    shutil.copytree(source_sql, target_sql)
    return ProjectPaths.from_root(tmp_path)


def test_project_paths_default_to_working_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)

    paths = ProjectPaths.from_root()

    assert paths.root == tmp_path.resolve()
    assert paths.sql == tmp_path.resolve() / "sql"


def test_pipeline_is_idempotent_and_creates_all_layers(tmp_path: Path) -> None:
    paths = temporary_project(tmp_path)
    first = run_pipeline(paths, payload=source_payload())
    second = run_pipeline(paths, payload=source_payload())

    connection = duckdb.connect(str(paths.database), read_only=True)
    event_count = connection.execute("SELECT COUNT(*) FROM earthquakes").fetchone()[0]
    run_count = connection.execute("SELECT COUNT(*) FROM pipeline_runs").fetchone()[0]
    connection.close()

    assert first.extracted == 2
    assert first.accepted == 1
    assert first.rejected == 1
    assert first.quality_passed
    assert second.quality_passed
    assert event_count == 1
    assert run_count == 2
    assert first.bronze_path.exists()
    assert first.silver_path and first.silver_path.exists()
    assert first.dashboard_path.exists()
    assert "QuakeFlow" in first.dashboard_path.read_text(encoding="utf-8")
    assert len(list(paths.rejects.rglob("*.jsonl"))) == 2
