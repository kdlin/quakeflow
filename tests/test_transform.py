from datetime import UTC, datetime

import pytest

from quakeflow.transform import Earthquake, InvalidEarthquake, extract_region, magnitude_band


def feature(event_id: str = "us-test") -> dict:
    return {
        "type": "Feature",
        "id": event_id,
        "properties": {
            "mag": 5.4,
            "place": "12 km NE of Testville, California",
            "time": 1_765_843_200_000,
            "updated": 1_765_843_260_000,
            "type": "earthquake",
            "alert": "green",
            "tsunami": 0,
            "felt": 42,
            "sig": 500,
            "url": "https://earthquake.usgs.gov/earthquakes/eventpage/us-test",
            "net": "us",
            "status": "reviewed",
        },
        "geometry": {"type": "Point", "coordinates": [-120.5, 35.3, 8.2]},
    }


def test_feature_maps_to_silver_schema() -> None:
    event = Earthquake.from_feature(feature(), datetime.now(UTC))

    assert event.event_id == "us-test"
    assert event.magnitude_band == "moderate"
    assert event.region == "California"
    assert event.longitude == -120.5
    assert event.tsunami is False


def test_missing_coordinates_are_rejected() -> None:
    source = feature()
    source["geometry"]["coordinates"] = []

    with pytest.raises(InvalidEarthquake, match="Geometry"):
        Earthquake.from_feature(source, datetime.now(UTC))


@pytest.mark.parametrize(
    ("magnitude", "expected"),
    [(1.9, "micro"), (3.2, "minor"), (4.8, "light"), (6.2, "strong"), (8.1, "great")],
)
def test_magnitude_bands(magnitude: float, expected: str) -> None:
    assert magnitude_band(magnitude) == expected


def test_region_fallback() -> None:
    assert extract_region("Northern Mid-Atlantic Ridge") == "Northern Mid-Atlantic Ridge"
