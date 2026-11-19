"""Command line interface (`weekend`)."""

from typing import Annotated

import typer

from app import __version__

_cli = typer.Typer(help="Weekendplanner", add_completion=False, no_args_is_help=True)


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


# Entrypoint name required by `weekend = "app.cli:app"`.
app = _cli
