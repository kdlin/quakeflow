from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


class InvalidEarthquake(ValueError):
    """Raised when a source event cannot satisfy the silver schema."""


def _timestamp(milliseconds: Any, field: str) -> datetime:
    if not isinstance(milliseconds, (int, float)):
        raise InvalidEarthquake(f"{field} must be epoch milliseconds")
    return datetime.fromtimestamp(milliseconds / 1000, tz=UTC)


def _optional_number(value: Any) -> float | None:
    if value is None:
        return None
    if not isinstance(value, (int, float)):
        raise InvalidEarthquake(f"Expected a numeric value, received {value!r}")
    return float(value)


def magnitude_band(magnitude: float | None) -> str:
    if magnitude is None:
        return "unknown"
    if magnitude < 2:
        return "micro"
    if magnitude < 4:
        return "minor"
    if magnitude < 5:
        return "light"
    if magnitude < 6:
        return "moderate"
    if magnitude < 7:
        return "strong"
    if magnitude < 8:
        return "major"
    return "great"


def extract_region(place: str) -> str:
    if not place:
        return "Unknown"
    return place.rsplit(",", maxsplit=1)[-1].strip()


@dataclass(frozen=True)
class Earthquake:
    event_id: str
    magnitude: float | None
    magnitude_band: str
    place: str
    region: str
    occurred_at: datetime
    updated_at: datetime
    longitude: float
    latitude: float
    depth_km: float
    event_type: str
    alert: str | None
    tsunami: bool
    felt: int | None
    significance: int | None
    detail_url: str | None
    source_net: str | None
    status: str | None
    ingested_at: datetime

    @classmethod
    def from_feature(cls, feature: dict[str, Any], ingested_at: datetime) -> Earthquake:
        if feature.get("type") != "Feature":
            raise InvalidEarthquake("Record is not a GeoJSON Feature")

        event_id = feature.get("id")
        if not isinstance(event_id, str) or not event_id.strip():
            raise InvalidEarthquake("Missing event id")

        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            raise InvalidEarthquake("Missing properties or geometry")

        coordinates = geometry.get("coordinates")
        if not isinstance(coordinates, list) or len(coordinates) < 3:
            raise InvalidEarthquake("Geometry must contain longitude, latitude, and depth")

        longitude, latitude, depth = (_optional_number(value) for value in coordinates[:3])
        if longitude is None or latitude is None or depth is None:
            raise InvalidEarthquake("Coordinates cannot be null")

        place = str(properties.get("place") or "Unknown location")
        magnitude = _optional_number(properties.get("mag"))

        return cls(
            event_id=event_id,
            magnitude=magnitude,
            magnitude_band=magnitude_band(magnitude),
            place=place,
            region=extract_region(place),
            occurred_at=_timestamp(properties.get("time"), "time"),
            updated_at=_timestamp(properties.get("updated"), "updated"),
            longitude=longitude,
            latitude=latitude,
            depth_km=depth,
            event_type=str(properties.get("type") or "unknown"),
            alert=properties.get("alert"),
            tsunami=bool(properties.get("tsunami", 0)),
            felt=int(properties["felt"]) if properties.get("felt") is not None else None,
            significance=(int(properties["sig"]) if properties.get("sig") is not None else None),
            detail_url=properties.get("url"),
            source_net=properties.get("net"),
            status=properties.get("status"),
            ingested_at=ingested_at,
        )


def transform_features(
    features: list[dict[str, Any]], ingested_at: datetime
) -> tuple[list[Earthquake], list[dict[str, Any]]]:
    accepted: list[Earthquake] = []
    rejected: list[dict[str, Any]] = []

    for feature in features:
        try:
            accepted.append(Earthquake.from_feature(feature, ingested_at))
        except (InvalidEarthquake, TypeError, ValueError) as error:
            rejected.append(
                {
                    "event_id": feature.get("id"),
                    "reason": str(error),
                    "feature": feature,
                }
            )

    return accepted, rejected
