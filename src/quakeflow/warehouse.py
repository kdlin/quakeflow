from __future__ import annotations

from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from quakeflow.config import ProjectPaths
from quakeflow.transform import Earthquake

EARTHQUAKE_COLUMNS = (
    "event_id",
    "magnitude",
    "magnitude_band",
    "place",
    "region",
    "occurred_at",
    "updated_at",
    "longitude",
    "latitude",
    "depth_km",
    "event_type",
    "alert",
    "tsunami",
    "felt",
    "significance",
    "detail_url",
    "source_net",
    "status",
    "ingested_at",
)


def connect(paths: ProjectPaths, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    paths.warehouse.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(paths.database), read_only=read_only)


def initialize(connection: duckdb.DuckDBPyConnection, paths: ProjectPaths) -> None:
    connection.execute((paths.sql / "schema.sql").read_text(encoding="utf-8"))
    connection.execute((paths.sql / "gold.sql").read_text(encoding="utf-8"))


def earthquake_row(event: Earthquake) -> tuple[object, ...]:
    return tuple(getattr(event, column) for column in EARTHQUAKE_COLUMNS)


def load_earthquakes(
    connection: duckdb.DuckDBPyConnection,
    events: Iterable[Earthquake],
    silver_root: Path,
    run_at: datetime,
) -> tuple[int, Path | None]:
    """Upsert validated events and emit a compressed silver Parquet partition."""
    rows = [earthquake_row(event) for event in events]
    if not rows:
        return 0, None

    connection.execute("DROP TABLE IF EXISTS staging_earthquakes")
    connection.execute(
        "CREATE TEMP TABLE staging_earthquakes AS SELECT * FROM earthquakes WHERE 1=0"
    )
    placeholders = ", ".join("?" for _ in EARTHQUAKE_COLUMNS)
    connection.executemany(
        f"INSERT INTO staging_earthquakes VALUES ({placeholders})",  # noqa: S608
        rows,
    )

    partition = silver_root / f"ingested_date={run_at:%Y-%m-%d}"
    partition.mkdir(parents=True, exist_ok=True)
    parquet_path = partition / f"earthquakes_{run_at:%Y%m%dT%H%M%S%fZ}.parquet"
    escaped_path = str(parquet_path).replace("'", "''")
    connection.execute(
        f"COPY staging_earthquakes TO '{escaped_path}' "  # noqa: S608
        "(FORMAT PARQUET, COMPRESSION ZSTD)"
    )

    connection.execute("INSERT OR REPLACE INTO earthquakes SELECT * FROM staging_earthquakes")
    return len(rows), parquet_path


def start_run(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
    feed: str,
    started_at: datetime,
) -> None:
    connection.execute(
        """
        INSERT INTO pipeline_runs (run_id, feed, started_at, status)
        VALUES (?, ?, ?, 'running')
        """,
        [run_id, feed, started_at],
    )


def finish_run(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
    status: str,
    extracted: int = 0,
    accepted: int = 0,
    rejected: int = 0,
    error_message: str | None = None,
) -> None:
    connection.execute(
        """
        UPDATE pipeline_runs
        SET completed_at = ?, extracted_count = ?, accepted_count = ?,
            rejected_count = ?, status = ?, error_message = ?
        WHERE run_id = ?
        """,
        [
            datetime.now(UTC),
            extracted,
            accepted,
            rejected,
            status,
            error_message,
            run_id,
        ],
    )
