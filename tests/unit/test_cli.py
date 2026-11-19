from typer.testing import CliRunner

import app
from app.cli import app as cli_app

runner = CliRunner()


def test_version_flag_prints_package_version_and_exits_zero() -> None:
    result = runner.invoke(cli_app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == app.__version__
