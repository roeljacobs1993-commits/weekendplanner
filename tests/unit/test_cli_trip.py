from pathlib import Path

from typer.testing import CliRunner

from app.cli import app as cli_app

runner = CliRunner()
EXAMPLE = Path(__file__).parents[2] / "trips" / "maart-2027.yaml"


def test_trip_check_shows_the_validated_trip_and_derived_nights() -> None:
    result = runner.invoke(cli_app, ["trip", "check", str(EXAMPLE)])

    assert result.exit_code == 0
    assert "maart-2027" in result.stdout
    assert "nights: 3" in result.stdout
    assert "group_size: 10" in result.stdout


def test_trip_check_applies_set_overrides() -> None:
    result = runner.invoke(cli_app, ["trip", "check", str(EXAMPLE), "--set", "top_n=10"])

    assert result.exit_code == 0
    assert "top_n: 10" in result.stdout


def test_trip_check_reports_field_errors_with_exit_code_2() -> None:
    result = runner.invoke(cli_app, ["trip", "check", str(EXAMPLE), "--set", "group_size=0"])

    assert result.exit_code == 2
    assert "group_size: Input should be greater than or equal to 1" in result.stderr


def test_trip_check_error_output_has_no_traceback(tmp_path: Path) -> None:
    result = runner.invoke(cli_app, ["trip", "check", str(tmp_path / "missing.yaml")])

    assert result.exit_code == 2
    assert "Traceback" not in result.output
    assert "not found" in result.stderr
