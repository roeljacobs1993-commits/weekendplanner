# Weekendplanner

Een lokale Python-tool die weekendtrip-bestemmingen rangschikt op vluchten, prijs, kwaliteit, activiteiten en originaliteit. Zie `docs/PROJECT_BRIEF.md` voor het doel en `docs/ARCHITECTURE.md` voor de opzet.

Deze repository is publiek: API-sleutels staan alleen in je eigen `.env` (nooit committen) en persoonlijke trip-bestanden horen in `trips/local/` (genegeerd door git).

Status: walking skeleton. Er is alleen `weekend --version` en een `/health`-endpoint; de rest volgt volgens `docs/PLAN.md`.

## Vereisten
- [uv](https://docs.astral.sh/uv/) (installeert zo nodig zelf Python 3.12 of nieuwer)
- Git

## Aan de slag (± 5 minuten)
```bash
git clone <repo-url> && cd <map>
uv sync                      # installeert Python en alle afhankelijkheden
cp .env.example .env         # vul daarna de waarden in (minimaal CONTACT_URL, een https-URL)
uv run weekend --version     # toont de versie
uv run pytest                # draait de tests met coverage
```

Alle controles lokaal (zoals in de CI):
```bash
uv run ruff format --check . && uv run ruff check . && uv run pyright && uv run pytest
uv run pre-commit install    # optioneel: dezelfde controles bij elke commit
```

## Beveiliging
Zie [SECURITY.md](SECURITY.md) voor het melden van een kwetsbaarheid.

## Licentie
MIT, zie [LICENSE](LICENSE).
