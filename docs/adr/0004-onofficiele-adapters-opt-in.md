# ADR-0004: Onofficiële adapters alleen met expliciete opt-in

- **Status**: voorgesteld
- **Datum**: 2026-11-19
- **Eisen**: brief "Scope" (optionele, onofficiële bronnen), "Databronnen"; SE-5, CQ-8, OB-1

## Context
Ryanair `farfnd` (via `ryanair-py`), `fast-flights` (Google Flights-scraper) en `pyairbnb` vullen gaten (kleine luchthavens, extra verblijven), maar zijn in strijd met de voorwaarden van de aanbieders en kunnen zonder aankondiging breken.

## Beslissing
- De repo is publiek (ADR-0006). Daarom staan de adapters **niet in de repo**. Ze zijn lokale plug-ins in `plugins/local/`, en die map staat in `.gitignore`.
  - De repo bevat alleen het plug-in-mechanisme: een `Protocol` per brontype, een loader en tests met een nep-plug-in.
  - De loader importeert `plugins/local/` alleen als `--allow-unofficial` (CLI) of het vinkje in de web-UI aan staat.
  - Er is **geen** omgevingsvariabele of configuratiewaarde die ze permanent aanzet.
- Bij gebruik: een waarschuwing op stderr en bovenaan het rapport, en elk resultaat uit deze bronnen krijgt het label `unofficial` en hoogstens betrouwbaarheid `cached`.
- Eigen, lage limieten (bijv. max. 30 verzoeken per run, ≥ 2 s tussen verzoeken) via dezelfde quotabewaking als de officiële bronnen.
- De packages (`ryanair-py`, `fast-flights`, `pyairbnb`) staan niet in `pyproject.toml` en niet in `uv.lock`.
  - De gebruiker installeert ze lokaal met `uv pip install` en controleert ze zelf met `pip-audit`. De README beschrijft hoe.
  - CI test alleen het plug-in-mechanisme.
- Een falende onofficiële adapter laat de run nooit falen: hij logt een warning en de pipeline gaat door zonder die bron (OB-1).

## Alternatieven
| Alternatief | Waarom niet |
|---|---|
| Niet aanbieden | Expliciet gevraagd in de brief; vult de dunne dekking van kleine luchthavens. |
| Standaard aan | Strijdig met voorwaarden; ongemerkt risico voor de gebruiker. |

## Gevolgen
- **Positief**: officiële route blijft schoon en voorspelbaar; extra dekking bewust beschikbaar.
- **Negatief**: extra onderhoud; de adapters kunnen breken. Tests draaien alleen tegen opgenomen responses.
- **Vervolgacties**: licentie en onderhoudsstatus van de drie packages vastleggen in de PR van T-014a/T-014b.
