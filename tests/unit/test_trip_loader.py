from datetime import date, time
from pathlib import Path

import pytest

from app.trips import TripFileError, apply_overrides, load_trip

REPO = Path(__file__).parents[2]
EXAMPLE = REPO / "trips" / "maart-2027.yaml"

MINIMAL = """\
name: minimal
home: {name: Nijmegen, lat: 51.8425, lon: 5.8528}
group_size: 10
rooms_min: 5
outbound: {date: 2027-03-19, earliest: "12:00", latest: "18:00"}
inbound: {date: 2027-03-22, earliest: "15:00"}
"""


def write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "trip.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_example_trip_for_march_2027_loads() -> None:
    trip = load_trip(EXAMPLE)

    assert trip.group_size == 10
    assert trip.rooms_min == 5
    assert trip.outbound.date == date(2027, 3, 19)
    assert trip.outbound.earliest == time(12, 0)
    assert trip.outbound.latest == time(18, 0)
    assert trip.inbound.date == date(2027, 3, 22)
    assert trip.inbound.earliest == time(15, 0)
    assert trip.max_drive_minutes == 150
    assert trip.max_ov_minutes == 180
    assert trip.nonstop_only is True


def test_override_replaces_a_top_level_value(tmp_path: Path) -> None:
    trip = load_trip(write(tmp_path, MINIMAL), overrides=["top_n=10"])

    assert trip.top_n == 10


def test_override_reaches_nested_values(tmp_path: Path) -> None:
    trip = load_trip(write(tmp_path, MINIMAL), overrides=["weights.price=0.6"])

    assert trip.weights.price == 0.6


def test_override_is_validated_again(tmp_path: Path) -> None:
    with pytest.raises(TripFileError) as exc_info:
        load_trip(write(tmp_path, MINIMAL), overrides=["top_n=4"])

    assert any(e.startswith("top_n:") for e in exc_info.value.errors)


def test_override_without_equals_sign_is_rejected() -> None:
    with pytest.raises(TripFileError, match="key=value"):
        apply_overrides({}, ["top_n"])


def test_override_cannot_descend_into_a_scalar() -> None:
    with pytest.raises(TripFileError, match="group_size is not a section"):
        apply_overrides({"group_size": 10}, ["group_size.extra=1"])


def test_validation_errors_are_reported_per_field(tmp_path: Path) -> None:
    text = MINIMAL.replace("group_size: 10", "group_size: 0")

    with pytest.raises(TripFileError) as exc_info:
        load_trip(write(tmp_path, text))

    assert exc_info.value.errors == ["group_size: Input should be greater than or equal to 1"]


def test_missing_file_is_a_trip_file_error(tmp_path: Path) -> None:
    with pytest.raises(TripFileError, match="not found"):
        load_trip(tmp_path / "missing.yaml")


def test_invalid_yaml_is_a_trip_file_error(tmp_path: Path) -> None:
    with pytest.raises(TripFileError, match="not valid YAML"):
        load_trip(write(tmp_path, "name: [unclosed"))


def test_yaml_that_is_not_a_mapping_is_rejected(tmp_path: Path) -> None:
    with pytest.raises(TripFileError, match="must contain a mapping"):
        load_trip(write(tmp_path, "- just\n- a list\n"))
