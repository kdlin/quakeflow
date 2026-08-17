from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from quakeflow.config import FEEDS, ProjectPaths
from quakeflow.dashboard import build_dashboard
from quakeflow.extract import fetch_geojson, persist_bronze, utc_now
from quakeflow.quality import QualityCheck, record_quality_results, run_quality_checks
from quakeflow.transform import transform_features
from quakeflow.warehouse import connect, finish_run, initialize, load_earthquakes, start_run


@dataclass(frozen=True)
class PipelineSummary:
    run_id: str
    feed: str
    extracted: int
    accepted: int
    rejected: int
    bronze_path: Path
    silver_path: Path | None
    dashboard_path: Path
    quality_checks: list[QualityCheck]

    @property
    def quality_passed(self) -> bool:
        return all(check.passed for check in self.quality_checks)


def _persist_rejects(rejected: list[dict], root: Path, run_at: datetime) -> Path | None:
    if not rejected:
        return None
    partition = root / f"ingested_date={run_at:%Y-%m-%d}"
    partition.mkdir(parents=True, exist_ok=True)
    target = partition / f"rejected_{run_at:%Y%m%dT%H%M%S%fZ}.jsonl"
    target.write_text(
        "\n".join(json.dumps(item, separators=(",", ":")) for item in rejected) + "\n",
        encoding="utf-8",
    )
    return target


def run_pipeline(
    paths: ProjectPaths,
    feed: str = "all_day",
    payload: dict | None = None,
    freshness_hours: int | None = 48,
) -> PipelineSummary:
    if feed not in FEEDS:
        raise ValueError(f"Unknown feed {feed!r}. Choose from: {', '.join(FEEDS)}")

    paths.ensure_directories()
    run_at = utc_now()
    run_id = str(uuid.uuid4())
    connection = connect(paths)
    initialize(connection, paths)
    start_run(connection, run_id, feed, run_at)

    extracted_count = accepted_count = rejected_count = 0
    try:
        source = payload if payload is not None else fetch_geojson(FEEDS[feed])
        bronze_path = persist_bronze(source, paths.bronze, run_at)
        features = source.get("features", [])
        if not isinstance(features, list):
            raise ValueError("GeoJSON features must be a list")

        extracted_count = len(features)
        accepted, rejected = transform_features(features, run_at)
        accepted_count = len(accepted)
        rejected_count = len(rejected)
        _persist_rejects(rejected, paths.rejects, run_at)

        _, silver_path = load_earthquakes(connection, accepted, paths.silver, run_at)
        checks = run_quality_checks(connection, freshness_hours=freshness_hours)
        record_quality_results(connection, run_id, checks)
        dashboard_path = build_dashboard(connection, paths.docs / "index.html")
        status = "success" if all(check.passed for check in checks) else "quality_warning"
        finish_run(
            connection,
            run_id,
            status,
            extracted_count,
            accepted_count,
            rejected_count,
        )
        return PipelineSummary(
            run_id=run_id,
            feed=feed,
            extracted=extracted_count,
            accepted=accepted_count,
            rejected=rejected_count,
            bronze_path=bronze_path,
            silver_path=silver_path,
            dashboard_path=dashboard_path,
            quality_checks=checks,
        )
    except Exception as error:
        finish_run(
            connection,
            run_id,
            "failed",
            extracted_count,
            accepted_count,
            rejected_count,
            str(error),
        )
        raise
    finally:
        connection.close()
