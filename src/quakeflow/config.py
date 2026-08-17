from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

FEEDS = {
    "all_hour": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_hour.geojson",
    "all_day": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_day.geojson",
    "all_week": "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/all_week.geojson",
    "significant_month": (
        "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_month.geojson"
    ),
}


@dataclass(frozen=True)
class ProjectPaths:
    root: Path
    data: Path
    bronze: Path
    silver: Path
    rejects: Path
    warehouse: Path
    database: Path
    docs: Path
    sql: Path

    @classmethod
    def from_root(cls, root: Path | str | None = None) -> ProjectPaths:
        project_root = Path(root).resolve() if root else Path(__file__).resolve().parents[2]
        data = project_root / "data"
        return cls(
            root=project_root,
            data=data,
            bronze=data / "bronze",
            silver=data / "silver",
            rejects=data / "rejects",
            warehouse=data / "warehouse",
            database=data / "warehouse" / "quakeflow.duckdb",
            docs=project_root / "docs",
            sql=project_root / "sql",
        )

    def ensure_directories(self) -> None:
        for directory in (
            self.bronze,
            self.silver,
            self.rejects,
            self.warehouse,
            self.docs,
        ):
            directory.mkdir(parents=True, exist_ok=True)
