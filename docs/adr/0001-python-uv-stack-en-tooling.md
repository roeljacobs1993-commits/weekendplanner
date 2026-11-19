# ADR-0001: Python 3.12 met uv, ruff, pyright en pytest

- **Status**: voorgesteld
- **Datum**: 2026-11-19
- **Eisen**: brief "Stack"; CQ-1, CQ-2, CQ-3, CQ-5, TS-4, CI-1, CI-2, CI-6, SE-3

## Context
De brief schrijft een Python CLI plus lokale web-UI voor. De standaarden eisen een formatter, linter zonder warnings, strikte typecontrole, coverage ≥ 80% (ook op gewijzigde regels), reproduceerbare builds met lockfile en dependency-audit. Het is een lokale tool voor één gebruiker op Windows; de CI draait op Linux.

## Beslissing
- **Runtime**: Python `>=3.12`, package `app` in `src/app/` (src-layout), entrypoint `weekend = "app.cli:app"`.
- **Pakketbeheer**: `uv` met `uv.lock` (gecommit). CI installeert met `uv sync --frozen`. Build met `uv build` (hatchling backend).
- **Opmaak en lint**: `ruff format` en `ruff check` met o.a. de regelsets `E, F, W, I, B, UP, S, C90 (max-complexity = 10), T20 (geen print), ERA (geen uitgecommentarieerde code), BLE (geen blind except), PT, SIM, RUF`.
- **Types**: `pyright` in `strict`-modus over `src/` en `tests/`.
- **Tests**: `pytest`, `pytest-cov` (`--cov-fail-under=80`), `diff-cover` (`--fail-under=80` tegen `origin/main`), `respx` voor het mocken van httpx aan de rand, `time-machine` of een geïnjecteerde `Clock` voor tijd. Netwerk is in tests geblokkeerd (`pytest-socket`, `--disable-socket`, met uitzondering voor localhost in de e2e-tests).
- **Libraries**: pydantic v2, pydantic-settings, httpx, structlog, Typer, FastAPI + Jinja2 + uvicorn, SQLAlchemy 2 + Alembic, PyYAML.
- **Security-scans**: `pip-audit` (op de geëxporteerde lockfile) en gitleaks in CI en pre-commit.
- **Lokaal**: pre-commit met ruff, pyright (lokale hook via `uv run`), gitleaks en standaard hygiene-hooks.

## Alternatieven
| Alternatief | Waarom niet |
|---|---|
| Poetry / pip-tools | Trager, en uv dekt lockfile, venv, Python-installatie en build in één tool. |
| mypy | Pyright is sneller en de standaard (CQ-3) noemt pyright expliciet. |
| black + flake8 + isort | Ruff vervangt ze alle drie, met één configuratie. |
| Click/argparse | Typer geeft type-annotated CLI's en zit in de brief. |

## Gevolgen
- **Positief**: één snelle toolchain; lokale en CI-controles zijn identiek (`uv run ...`).
- **Negatief**: pyright strict vraagt stubs of expliciete typering voor libraries zonder types (bijv. PyYAML via `types-PyYAML`). Elke `# pyright: ignore` krijgt een reden (CQ-3).
- **Vervolgacties**: nieuwe afhankelijkheden krijgen een korte afweging in de PR (CQ-8, AG-8).
