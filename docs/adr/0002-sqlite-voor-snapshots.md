# ADR-0002: SQLite in plaats van PostgreSQL voor snapshots, quota en historie

- **Status**: voorgesteld
- **Datum**: 2026-11-19
- **Eisen**: brief "Stack", "Buiten scope" (geen hosting, één gebruiker), NFR Determinisme; TS-7, OB-6; regel `rules/testing.md` ("integratietests tegen de echte PostgreSQL")

## Context
De tool bewaart ruwe API-responses (snapshots), quotatellers, groepshistorie en run-resultaten. Er is één gebruiker, geen server en geen cloudhosting. De testregel in `rules/testing.md` zegt dat integratietests tegen een echte PostgreSQL draaien en niet tegen SQLite; TS-7 (SHOULD) vraagt echte afhankelijkheden in containers in plaats van mocks.

## Beslissing
- Opslag in één **SQLite**-bestand (standaard `var/weekend.sqlite3`, instelbaar via `DATABASE_URL`, gitignored).
- Toegang via **SQLAlchemy 2** met gebonden parameters; schema uitsluitend via **Alembic**-migraties (OB-6). `render_as_batch=True` voor SQLite-compatibele `ALTER`s.
- **Afwijking van de testregel**: integratietests draaien tegen een **echt SQLite-bestand** in `tmp_path`, waarop eerst `alembic upgrade head` draait. Er wordt nooit een database gemockt. Omdat productie ook SQLite is, test dit precies de echte afhankelijkheid; de geest van TS-7 (geen mocks, echte engine) blijft overeind.
- We gebruiken geen PostgreSQL-specifieke features; JSON wordt als `JSON`-kolom (SQLite JSON1) opgeslagen.

## Alternatieven
| Alternatief | Waarom niet |
|---|---|
| PostgreSQL lokaal (Docker) | Vereist Docker/een service op de Windows-laptop van één gebruiker; botst met "binnen 5 minuten lokaal draaien" (DO-1). Geen enkel voordeel bij één gebruiker en kleine data. |
| PostgreSQL alleen in tests | Dan test je een andere engine dan in productie; dat is juist wat de regel wil voorkomen. |
| Losse JSON-bestanden | Geen transacties voor de quotateller (race bij gelijktijdige CLI en web-UI), lastig opschonen per bewaartermijn. |

## Gevolgen
- **Positief**: nul installatie, snel, deterministisch, eenvoudig te back-uppen of te verwijderen.
- **Negatief**: beperkte gelijktijdigheid; CLI en web-UI tegelijk schrijven kan `database is locked` geven. Mitigatie: WAL-modus en korte transacties; quotum ophogen gebeurt atomair in één `UPDATE ... SET used = used + 1 WHERE used < limit`.
- **Vervolgacties**: bij een eventuele overstap naar meerdere gebruikers of hosting (nu buiten scope) wordt deze ADR herzien.
