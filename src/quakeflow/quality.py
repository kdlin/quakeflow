from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

import duckdb


@dataclass(frozen=True)
class QualityCheck:
    name: str
    passed: bool
    observed: str
    expectation: str


def run_quality_checks(
    connection: duckdb.DuckDBPyConnection,
    freshness_hours: int | None = 48,
) -> list[QualityCheck]:
    checks: list[QualityCheck] = []

    total, unique_ids = connection.execute(
        "SELECT COUNT(*), COUNT(DISTINCT event_id) FROM earthquakes"
    ).fetchone()
    checks.append(
        QualityCheck(
            "event_id_uniqueness",
            total == unique_ids,
            f"{unique_ids}/{total} unique",
            "Every event_id is unique",
        )
    )

    null_ids = connection.execute(
        "SELECT COUNT(*) FROM earthquakes WHERE event_id IS NULL OR event_id = ''"
    ).fetchone()[0]
    checks.append(QualityCheck("event_id_not_null", null_ids == 0, str(null_ids), "0 null ids"))

    invalid_coordinates = connection.execute(
        """
        SELECT COUNT(*) FROM earthquakes
        WHERE latitude NOT BETWEEN -90 AND 90 OR longitude NOT BETWEEN -180 AND 180
        """
    ).fetchone()[0]
    checks.append(
        QualityCheck(
            "coordinate_bounds",
            invalid_coordinates == 0,
            str(invalid_coordinates),
            "0 coordinates outside geographic bounds",
        )
    )

    invalid_magnitudes = connection.execute(
        "SELECT COUNT(*) FROM earthquakes WHERE magnitude NOT BETWEEN -2 AND 10"
    ).fetchone()[0]
    checks.append(
        QualityCheck(
            "magnitude_bounds",
            invalid_magnitudes == 0,
            str(invalid_magnitudes),
            "0 magnitudes outside [-2, 10]",
        )
    )

    invalid_depths = connection.execute(
        "SELECT COUNT(*) FROM earthquakes WHERE depth_km NOT BETWEEN -20 AND 800"
    ).fetchone()[0]
    checks.append(
        QualityCheck(
            "depth_bounds",
            invalid_depths == 0,
            str(invalid_depths),
            "0 depths outside [-20, 800] km",
        )
    )

    if freshness_hours is not None and total:
        hours_old = connection.execute(
            "SELECT date_diff('hour', MAX(occurred_at), current_timestamp) FROM earthquakes"
        ).fetchone()[0]
        checks.append(
            QualityCheck(
                "data_freshness",
                hours_old <= freshness_hours,
                f"{hours_old} hours",
                f"Latest event is no more than {freshness_hours} hours old",
            )
        )

    return checks


def record_quality_results(
    connection: duckdb.DuckDBPyConnection,
    run_id: str,
    checks: list[QualityCheck],
) -> None:
    connection.executemany(
        "INSERT INTO quality_results VALUES (?, ?, ?, ?, ?, ?)",
        [
            (run_id, check.name, check.passed, check.observed, check.expectation, datetime.now(UTC))
            for check in checks
        ],
    )
