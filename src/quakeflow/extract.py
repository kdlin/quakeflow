from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

USER_AGENT = "QuakeFlow/1.0 (https://github.com/kdlin/quakeflow)"


def fetch_geojson(url: str, retries: int = 3, timeout: int = 30) -> dict[str, Any]:
    """Fetch a USGS GeoJSON feed with bounded exponential backoff."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_error: Exception | None = None

    for attempt in range(retries):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                if response.status != 200:
                    raise RuntimeError(f"USGS returned HTTP {response.status}")
                payload = json.load(response)
                if payload.get("type") != "FeatureCollection":
                    raise ValueError("Expected a GeoJSON FeatureCollection")
                return payload
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as error:
            last_error = error
            if attempt < retries - 1:
                time.sleep(2**attempt)

    raise RuntimeError(f"Unable to fetch USGS feed after {retries} attempts") from last_error


def persist_bronze(payload: dict[str, Any], bronze_root: Path, run_at: datetime) -> Path:
    """Persist the unmodified API response as an immutable bronze artifact."""
    partition = bronze_root / f"ingested_date={run_at:%Y-%m-%d}"
    partition.mkdir(parents=True, exist_ok=True)
    target = partition / f"earthquakes_{run_at:%Y%m%dT%H%M%S%fZ}.json"
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target


def utc_now() -> datetime:
    return datetime.now(UTC)
