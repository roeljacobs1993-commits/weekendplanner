"""Command line interface (`weekend`)."""

from pathlib import Path
from typing import Annotated

import typer
import yaml

from app import __version__
from app.trips import TripFileError, load_trip

_cli = typer.Typer(help="Weekendplanner", add_completion=False, no_args_is_help=True)
_trip = typer.Typer(help="Work with trip files.", no_args_is_help=True)
_cli.add_typer(_trip, name="trip")

# Exit code for invalid user input, matching the usage-error convention of Click.
EXIT_INVALID_INPUT = 2


def _show_version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit


@_cli.callback()
def main(
    version: Annotated[
        bool,
        typer.Option("--version", callback=_show_version, is_eager=True, help="Show the version."),
    ] = False,
) -> None:
    """Weekendplanner command line."""


@_trip.command("check")
def trip_check(
    path: Annotated[Path, typer.Argument(help="Trip file (YAML).")],
    overrides: Annotated[
        list[str] | None,
        typer.Option(
            "--set",
            help=(
                "Override a value, e.g. --set top_n=10 or weights.price=0.5. Values are read as"
                " YAML: quote text such as 'no' and times such as '\"12:00\"'; use null to clear."
            ),
        ),
    ] = None,
) -> None:
    """Validate a trip file and show the resulting configuration."""
    try:
        trip = load_trip(path, overrides or [])
    except TripFileError as exc:
        typer.echo(f"Error: {exc}", err=True)
        for error in exc.errors:
            if error != str(exc):
                typer.echo(f"  - {error}", err=True)
        raise typer.Exit(EXIT_INVALID_INPUT) from exc
    shown = trip.model_dump(mode="json") | {
        "nights": trip.nights,
        "required_bedrooms": trip.required_bedrooms,
        "required_guests": trip.required_guests,
    }
    typer.echo(yaml.safe_dump(shown, sort_keys=False, allow_unicode=True).rstrip())


# Entrypoint name required by `weekend = "app.cli:app"`.
app = _cli
