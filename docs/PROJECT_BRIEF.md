# Projectbrief: Weekendplanner

## Doel
Een herbruikbare tool waarmee een organisator groepsweekendjes plant. Je geeft variabelen mee: data, tijdvensters, groepsgrootte, vertreklocatie, eisen aan het verblijf en gewichten. De tool geeft dan een gerangschikte lijst van **3, 5 of 10 bestemmingen** terug. Elke bestemming krijgt een rating van 0 tot 10 op vier dimensies, plus een totaalscore en een uitleg:

- **prijs**
- **kwaliteit**
- **activiteiten**
- **originaliteit**

De vluchten zijn leidend. Een bestemming zonder geschikte directe heen- én terugvlucht valt af.

## Eerste use case (ijkpunt)
| Variabele | Waarde |
|---|---|
| Groep | 10 personen |
| Data | vr 19 maart 2027 – ma 22 maart 2027 (3 nachten) |
| Heenvlucht | vertrek 19-03 tussen 12:00 en 18:00 |
| Terugvlucht | vertrek 22-03 na 15:00 |
| Vluchten | alleen direct (non-stop) |
| Vertrekpunt | Nijmegen |
| Luchthavens | maximaal 2,5 uur rijden **en** maximaal 3 uur met het OV vanaf Nijmegen. Heen en terug mogen via verschillende luchthavens. |
| Verblijf | minimaal 5 slaapkamers (2 personen per kamer, ≥ 10 slaapplaatsen) en een grote gezamenlijke ruimte |

## Scope
**Wel in scope**
- CLI (`weekend rank <trip.yaml> --top N`) en een lokale web-UI met een formulier en resultaten.
- Kandidaat-vertrekluchthavens bepalen en filteren op rij- en OV-tijd.
- Directe vluchten zoeken binnen de tijdvensters, inclusief combinaties waarbij je via de ene luchthaven heen gaat en via een andere terugkomt (open-jaw).
- Weerverwachting op basis van klimatologie (30 jaar historische data rond de reisdatum).
- Verblijven met de juiste kamers en capaciteit, via een API en via handmatige CSV-import.
- Activiteitenscore en originaliteitsscore, inclusief groepshistorie (eerder bezochte bestemmingen tellen minder zwaar).
- Snapshots van alle opgehaalde data en quotabewaking per API, zodat je offline kunt herberekenen.
- Prijsalarm: periodiek opnieuw zoeken voor de shortlist en melden wanneer een prijs daalt.
- Optionele, onofficiële bronnen. Die staan standaard uit en zijn duidelijk gemarkeerd.

**Buiten scope**
- Boeken of betalen. De tool geeft alleen advies en links.
- Commerciële inzet of meerdere gebruikers. Het is een lokale tool voor één organisator.
- Hosting in de cloud.

## Stack
- Python 3.12+ met `uv`. Ruff voor opmaak en linting, pyright in strict-modus, pytest met coverage.
- pydantic / pydantic-settings, httpx, structlog, Typer (CLI), FastAPI + Jinja2 (web-UI), SQLAlchemy + Alembic op SQLite.
- GitHub (publieke repo, MIT-licentie; voorlopig alleen lokaal, zie ADR-0006) met GitHub Actions, release-please en Dependabot.

## Databronnen
Er komen alleen gratis API's of gratis tiers in. Onderzocht op 2026-11-19.

| Onderdeel | Bron | Opmerking |
|---|---|---|
| Vertrekluchthavens | statische tabel `data/airports.yaml` | Rijtijd eenmalig berekend met de OpenRouteService-matrix. OV-tijd uit een gecontroleerde tabel, te verversen via Transitous (alle luchthavens) en de NS API (controle voor de NL-luchthavens). |
| Routes en indicatieve prijzen | Travelpayouts / Aviasales Data API | Gratis token. Prijzen zijn gecachet (2–7 dagen oud). |
| Live vluchten | SerpApi Google Flights | 250 gratis zoekopdrachten per maand, gedeeld met hotels. Alleen voor de shortlist. |
| Verblijf | SerpApi Google Hotels (`vacation_rentals`, `bedrooms`) en CSV-import | Schatting uit Inside Airbnb-data. De woonkamer controleer je zelf of via een heuristiek. |
| Weer | Open-Meteo Archive | CC BY 4.0, bronvermelding verplicht. Alleen niet-commercieel. |
| Activiteiten | OSM Overpass en Wikivoyage | ODbL / CC BY-SA, bronvermelding verplicht. |
| Originaliteit | Wikimedia Pageviews, OSM-dichtheid en groepshistorie | User-Agent met contact-URL verplicht. |
| Geocoding | Nominatim | Maximaal 1 verzoek per seconde, resultaten gecachet. |
| Optioneel, onofficieel | Ryanair `farfnd`, `fast-flights`, `pyairbnb` | Lokale plug-ins in `plugins/local/`, buiten de publieke repo. Gaan alleen aan met `--allow-unofficial`. Ze zijn in strijd met de voorwaarden van de aanbieder, dus alleen voor persoonlijk gebruik met laag volume. |

Niet beschikbaar of afgevallen:
- Amadeus Self-Service (gestopt per 17-07-2026).
- Kiwi Tequila, Skyscanner, Booking.com Demand en Vrbo (alleen voor partners).
- OpenFlights (data uit 2014).

## Niet-functionele eisen
- **Quotum:** de tool overschrijdt nooit stilletjes een gratis quotum. Er komt een waarschuwing bij 80% en een harde stop bij 100%. Elke API-response wordt opgeslagen in een snapshot.
- **Determinisme:** dezelfde snapshot en dezelfde gewichten geven dezelfde ranking. Tests draaien zonder netwerk.
- **Transparantie:** elke score toont waar hij op gebaseerd is en hoe betrouwbaar dat is: live, gecachet of geschat.
- **Prestaties:** een volledige run met een warme cache duurt minder dan 30 seconden. Een koude run mag langer duren, door de rate limits.
- **Security:** API-keys alleen via `.env`, die niet in git komt. De sleutels staan zonder waarden in `.env.example` en worden bij het opstarten gevalideerd.
- **Toegankelijkheid:** de web-UI voldoet aan WCAG 2.2 AA.
- **Licenties:** de bronvermeldingen voor OSM, Open-Meteo en Wikimedia staan in de UI en in het rapport.

## Privacy (AVG)
- **Welke gegevens:** de tool verwerkt geen persoonsgegevens van deelnemers. Hij werkt alleen met aantallen.
- **Groepshistorie:** bevat alleen bestemmingen en datums.
- **User-Agent:** de contactgegevens zijn een repo-URL, geen persoonlijk e-mailadres.
- **Bewaartermijn snapshots:** standaard 12 maanden, instelbaar.

## Rollen
| Rol | Uitvoering |
|---|---|
| Opdrachtgever | Roel |
| Projectleider | hoofdsessie van Claude Code |
| Architect | `architect`-agent |
| Senior programmeur (review) | `code-reviewer`- en `security-auditor`-agent |
| Junior programmeur (bouw) | `general-purpose`-agent |
