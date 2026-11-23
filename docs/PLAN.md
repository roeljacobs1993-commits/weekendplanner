# Takenplan

Volgt het goedgekeurde plan (T-001…T-016). Te grote taken zijn gesplitst met een letter (bijv. T-009a), zodat de nummering herkenbaar blijft. Elke taak is één PR op `feat/<onderwerp>` of `chore/<onderwerp>`, met tests (TS-1), groene `ci` en review door `code-reviewer` en `security-auditor` (AG-4). Nieuwe configuratiesleutels komen leeg in `.env.example` en worden in `Settings` gevalideerd. Nieuwe afhankelijkheden krijgen een afweging in de PR.

## Mijlpaal 0: Fundament

### T-001: Walking skeleton
- **Doel**: een draaiend, getest en volledig door CI bewaakt leeg project, zodat elke volgende taak alleen nog functionaliteit toevoegt.
- **Acceptatiecriteria**:
  - [ ] Bestaande git-repo (branch `main` bestaat al) gebruikt; werk op `chore/walking-skeleton`.
  - [ ] `pyproject.toml` met `requires-python = ">=3.12"`, package `app` in `src/app/`, script `weekend = "app.cli:app"`; `uv.lock` gecommit; `uv sync --frozen` werkt op een schone checkout.
  - [ ] `uv run weekend --version` print de versie uit `app.__version__` en eindigt met exitcode 0 (test met `typer.testing.CliRunner`).
  - [ ] FastAPI-app in `src/app/web/app.py`: `GET /health` geeft 200 met `{"status": "ok", "version": "<versie>"}` (test met `TestClient`).
  - [ ] `src/app/config.py` met `Settings` (pydantic-settings, leest `.env`): `SERPAPI_KEY`, `TRAVELPAYOUTS_TOKEN`, `NS_API_KEY`, `ORS_API_KEY` als optionele `SecretStr` met formaatvalidatie wanneer gezet (niet-leeg, geen spaties, minimale lengte); `CONTACT_URL` verplicht, `https://`-URL, weigert `mailto:`/e-mailadressen; `LOG_LEVEL`, `LOG_FORMAT` met defaults. Tests: geldige config, ontbrekende `CONTACT_URL`, ongeldige key-vorm, e-mail als contact geweigerd. Geen andere module leest `os.environ` (ruff-regel of test die daarop greppt).
  - [ ] `.env.example` bevat alle sleutels zonder waarden; `.gitignore` bevat `.env`, `var/`, `stays/`, `.venv/`, caches, `dist/`.
  - [ ] Ruff (format + lint, regelsets uit ADR-0001 incl. `C90` max 10, `T20`, `ERA`, `S`, `BLE`) en pyright `strict` zonder fouten of warnings.
  - [ ] Pytest met `--cov=app --cov-fail-under=80`, `pytest-socket` (netwerk uit) en een `diff-cover`-stap (`--fail-under=80` tegen `origin/main`).
  - [ ] `.pre-commit-config.yaml` met ruff-format, ruff, pyright (lokaal via `uv run`), gitleaks, `no-commit-to-branch` (main), trailing-whitespace/end-of-file/check-yaml; `pre-commit run --all-files` slaagt.
  - [ ] `.github/workflows/ci.yml` op `pull_request` en `push` naar `main`, `permissions: contents: read`, jobs `format`, `lint`, `typecheck`, `test` (coverage + diff-cover, `fetch-depth: 0`), `build` (`uv build`), `gitleaks`, `pip-audit` (op `uv export --frozen --no-dev`), en een aggregerende job `ci` met `needs:` op alle jobs die faalt als één ervan faalt of wordt overgeslagen (`if: always()` + controle op `needs.*.result`). Caching van uv aan.
  - [ ] Alle actions vastgepind op een volledige commit-SHA met versie als commentaar; SHA's opgezocht met `git ls-remote --tags https://github.com/<owner>/<repo>` op het moment van implementeren (niet uit het geheugen).
  - [ ] `release-please-config.json`, `.release-please-manifest.json` (start `0.1.0`, type `python`) en `.github/workflows/release-please.yml` met minimale `permissions` (`contents: write`, `pull-requests: write` alleen op die job).
  - [ ] `.github/dependabot.yml` voor `uv` (of `pip` als uv-ecosystem niet beschikbaar is) en `github-actions`, wekelijks.
  - [ ] `SECURITY.md` (melden via GitHub private vulnerability reporting of security-advisory; geen persoonlijk e-mailadres), `README.md` in het Nederlands: wat het doet, vereisten, `uv sync`, `.env` vullen, `uv run weekend --version`, `uv run pytest`, binnen 5 minuten te volgen. `CODEOWNERS` optioneel.
  - [ ] `LICENSE` (MIT); `.gitignore` bevat ook `trips/local/` en `plugins/local/`; `.github/workflows/codeql.yml` (los van `ci`).
  - [ ] Lokaal (ADR-0006): de volledige controle is groen en de branch is met squash gemerged in `main` na review. **Uitgesteld tot akkoord op de eerste push**: een publieke GitHub-repo, branch protection op `main`, secret scanning met push protection, en een groene `ci`-check op de PR.
- **Afhankelijk van**: —
- **Omvang**: L

### T-002: Domeinmodellen en trip-config
- **Doel**: de trip-variabelen uit de brief als gevalideerd model laden uit YAML, zodat alle latere stappen met één betrouwbare invoer werken.
- **Acceptatiecriteria**:
  - [ ] Pydantic-modellen `TripConfig`, `TimeWindow`, `Weights`, `StayRequirements`, `GeoPoint` en `Confidence` in `src/app/domain/`, conform `ARCHITECTURE.md` §5.
  - [ ] Validatie: `inbound.date > outbound.date`; `earliest < latest` binnen een venster; `group_size ≥ 1`; `rooms_min × persons_per_room ≥ group_size`; `top_n ∈ {3, 5, 10}`; gewichten ≥ 0 met som > 0; `top_k_live ≥ top_n`. Elke regel heeft een test met een duidelijke foutmelding.
  - [ ] `trips/maart-2027.yaml` met de ijkpunt-waarden uit de brief laadt foutloos (test).
  - [ ] `weekend trip check <file>` toont de gevalideerde config (incl. afgeleide waarden zoals aantal nachten) of geeft per veld een leesbare fout en exitcode 2, zonder stacktrace.
  - [ ] CLI-vlaggen `--set key=value` overschrijven YAML-waarden en worden opnieuw gevalideerd (test).
  - [ ] structlog-configuratie in `src/app/logging.py` (JSON/console, niveau, `run_id` via contextvars, redactie-processor voor `key|token|secret|password`), met tests voor de redactie.
- **Afhankelijk van**: T-001
- **Omvang**: M

### T-003: Scoring-engine
- **Doel**: de vier dimensies, het totaal, de betrouwbaarheid en de uitleg als pure, volledig geteste functies, zodat de ranking los van de bronnen klopt.
- **Acceptatiecriteria**:
  - [ ] Modellen `FlightLeg`, `Itinerary`, `Stay`, `DimensionScore`, `DestinationScores`, `ScoringParams` toegevoegd.
  - [ ] Functies voor prijs, kwaliteit (incl. vlucht-gemak, weer, verblijf), activiteiten en originaliteit volgens de formules in `ARCHITECTURE.md` §6; elke formule getest op randwaarden (0 en 10 grenzen, begrenzing) en een representatief tussenpunt.
  - [ ] Ontbrekende invoer geeft 5,0 met betrouwbaarheid `estimated` en uitleg "geen data"; betrouwbaarheid van een dimensie is de laagste van de invoer (test).
  - [ ] Gewogen totaal en sortering (totaal ↓, prijs ↓, `city_code` ↑); dezelfde invoer in andere volgorde geeft dezelfde ranking (test).
  - [ ] `ScoringParams` overschrijfbaar via de trip-YAML (test).
  - [ ] Uitlegteksten in het Nederlands met bedragen en bron-betrouwbaarheid (snapshot-test op de string).
  - [ ] Geen I/O-imports in `src/app/scoring/` (test of lintregel).
- **Afhankelijk van**: T-002
- **Omvang**: M

### T-004: Snapshotopslag, quotabewaking en bronclient
- **Doel**: één gedeelde HTTP-laag die elke response bewaart, quota bewaakt en offline herberekenen mogelijk maakt, zodat geen adapter dit zelf hoeft te doen.
- **Acceptatiecriteria**:
  - [ ] SQLAlchemy-modellen en eerste Alembic-migratie voor `snapshot`, `quota_usage`, `run`, `run_snapshot`; `DATABASE_URL` (default `sqlite:///var/weekend.sqlite3`) in `Settings` en `.env.example`; WAL-modus aan.
  - [ ] Integratietest: `alembic upgrade head` en `downgrade base` op een echt SQLite-bestand in `tmp_path` (ADR-0002).
  - [ ] `SourceClient` (httpx): timeouts, User-Agent met `CONTACT_URL`, retry met backoff op 429/5xx (max 3, met geïnjecteerde sleep/clock in tests), rate limit per bron.
  - [ ] Cache: binnen TTL geen netwerkverzoek en geen quotaverbruik (test met respx: 0 calls).
  - [ ] Quotum: atomaire ophoging; bij 80% één `quota_warning`-log; bij 100% `QuotaExceededError` zonder netwerkverzoek (tests); `SERPAPI_MONTHLY_LIMIT` in `Settings`.
  - [ ] Elke response (ook 4xx/5xx) wordt als snapshot opgeslagen; request-params en URL's zijn geredigeerd (`api_key`, `token`): test dat een secret nergens in de snapshot of in de logs voorkomt. `httpx`/`httpcore`-loggers op WARNING.
  - [ ] De CLI roept bij het opstarten `configure_logging` aan met `known_secrets` uit alle gezette API-keys in `Settings` (ook hun URL-gecodeerde vorm). Een test bewijst dat een geconfigureerde key niet in de logs verschijnt.
  - [ ] Offline-modus: alleen snapshots; ontbrekende snapshot geeft `OfflineMissError`, geen netwerk (test).
  - [ ] `weekend quota` toont verbruik per bron en periode; `weekend snapshots prune` met `SNAPSHOT_RETENTION_MONTHS` (default 12), vraagt bevestiging, `--yes` om te skippen (tests met fake clock).
- **Afhankelijk van**: T-002
- **Omvang**: L

## Mijlpaal 1: Vluchten

### T-005: Vertrekluchthavens
- **Doel**: de toegestane vertrekluchthavens bepalen op rij- en OV-tijd vanaf de thuislocatie.
- **Acceptatiecriteria**:
  - [ ] `data/airports.yaml` met AMS, EIN, RTM, DUS, NRN, DTM, CGN, FMO, MST, BRU, CRL, GRQ, PAD: IATA, naam, land, coördinaten, `drive_minutes`, `drive_km`, `ov_minutes`, `ov_source` (`table`/`ns`), `ov_checked_at`, `ov_fare_eur`, `parking_eur_per_day`; geladen als `Airport`-modellen met validatie (test).
  - [ ] Pure filterfunctie: `drive ≤ max_drive_minutes` **en** `ov ≤ max_ov_minutes`; tests op de grenzen (precies 150/180 minuten = toegestaan).
  - [ ] Transitous-adapter (`/api/v5/plan`, `arriveBy=true`, User-Agent met `CONTACT_URL`, ≤ 720 verzoeken per dag, bronvermelding) voor de OV-tijd naar alle luchthavens.
  - [ ] ORS-matrix-adapter en NS-adapter (controle voor de NL-luchthavens) via `SourceClient`, getest tegen opgenomen responses (respx); `weekend airports refresh` herberekent waarden en schrijft het YAML-bestand terug (alleen met keys; zonder key een duidelijke melding).
  - [ ] `weekend airports list --trip <file>` toont alle luchthavens met tijden en of ze toegestaan zijn, met reden.
  - [ ] Bronvermelding openrouteservice en Transitous in `report/attributions.py`.
- **Afhankelijk van**: T-004
- **Omvang**: M

### T-006: Travelpayouts-adapter (routes en indicatieve prijzen)
- **Doel**: trap 1 van de trechter: voor elke toegestane luchthaven de directe bestemmingen met gecachte prijzen op de reisdata.
- **Acceptatiecriteria**:
  - [ ] Adapter implementeert `RoutePriceSource`; responses gevalideerd met pydantic; `TRAVELPAYOUTS_TOKEN` via header (niet in URL waar de API dat toestaat).
  - [ ] Geeft per (luchthaven, bestemming) indicatieve one-way prijzen heen en terug met `confidence = cached` en de leeftijd van de prijs.
  - [ ] Statische `airports.json`/`cities.json` (30 dagen cache) mappen luchthavens naar bestemmingssteden, incl. steden met meerdere luchthavens (test met MIL of LON-fixture).
  - [ ] Alleen directe vluchten (`direct=true`); routes zonder prijs worden gemarkeerd, niet weggegooid.
  - [ ] Tests tegen opgenomen fixtures: normaal, leeg resultaat, foutresponse (logt en gaat door).
- **Afhankelijk van**: T-005
- **Omvang**: M

### T-007a: SerpApi Google Flights-adapter
- **Doel**: live, non-stop vluchten voor de groep binnen de tijdvensters ophalen met zo weinig mogelijk zoekopdrachten.
- **Acceptatiecriteria**:
  - [ ] Adapter implementeert `LiveFlightSource`: one-way (`type=2`), `departure_id`/`arrival_id` met komma-gescheiden luchthavens, `stops=1`, `adults=group_size`, `outbound_times` uit het tijdvenster, `currency=EUR`.
  - [ ] Eén zoekopdracht per richting per bestemmingsstad (test telt respx-calls).
  - [ ] Resultaten buiten het tijdvenster of met tussenstops worden gefilterd (ook als de API ze toch teruggeeft; test).
  - [ ] Leeg resultaat op de terugdatum geeft status `possibly_not_on_sale` (test).
  - [ ] Telt tegen het gedeelde SerpApi-quotum; `SERPAPI_KEY` verschijnt niet in snapshot of log (test).
- **Afhankelijk van**: T-006
- **Omvang**: M

### T-007b: Itinerary-opbouw en top-K-trechter
- **Doel**: heen- en terugvluchten combineren tot de beste itinerary per stad (incl. open-jaw) en de live validatie beperken tot de top-K.
- **Acceptatiecriteria**:
  - [ ] Pure functie bouwt per stad de goedkoopste geldige combinatie, ook met verschillende vertrek- en aankomstluchthavens; `is_open_jaw` correct gezet (tests).
  - [ ] Grondvervoerkosten: auto bij zelfde luchthaven, OV bij open-jaw, volgens §4 (tests).
  - [ ] Vlag `group_booking_likely` bij `group_size ≥ 10` en maatschappij in `group_booking_airlines` (test).
  - [ ] Pipeline-stappen 1–4: voorselectie op voorlopige score, top-K (default 12), quotabudget (2 × K voor vluchten) vooraf gecontroleerd; bij te weinig quotum stopt de run vóór stap 4 met een melding die `--top-k` voorstelt (test).
  - [ ] Bestemmingen zonder geldige heen- of terugvlucht vallen af met reden; bij bronfout blijft de bestemming met `cached` en label "niet live bevestigd" (tests).
  - [ ] Integratietest: pipeline tot en met stap 4 offline op fixture-snapshots geeft een vaste lijst itineraries.
- **Afhankelijk van**: T-003, T-007a
- **Omvang**: L

## Mijlpaal 2: Overige factoren

### T-008: Weer (Open-Meteo-klimatologie)
- **Doel**: een weerscore per bestemming op basis van 30 jaar historische data rond de reisdata.
- **Acceptatiecriteria**:
  - [ ] Adapter implementeert `ClimateSource`: één archive-request per bestemming (1995–2024, `temperature_2m_max`, `sunshine_duration`, `precipitation_sum`), filter op ±3 dagen rond de reisdata; cache zonder vervaldatum.
  - [ ] Aggregatie (mediaan Tmax, mediaan zonuren, fractie regendagen ≥ 1 mm) als pure functie getest met een kleine fixture.
  - [ ] Weerscore volgt §6 en levert `confidence = cached` met uitleg ("mediaan 14 °C, 5,1 u zon, 30% regendagen").
  - [ ] Bronvermelding Open-Meteo (CC BY 4.0) in `ATTRIBUTIONS`.
- **Afhankelijk van**: T-007b
- **Omvang**: S

### T-009a: Verblijf: CSV-import en eis-check
- **Doel**: handmatig gevonden verblijven kunnen invoeren en toetsen aan de kamereisen, als betrouwbare basis naast de API's.
- **Acceptatiecriteria**:
  - [ ] `weekend stays import <csv>`: kolommen `city_code, name, bedrooms, guests, living_room (yes/no/unknown), price_total_eur, url, rating`; ongeldige rijen worden per regelnummer gemeld, geldige worden opgeslagen (tests).
  - [ ] Pure eis-check: `bedrooms ≥ rooms_min`, `guests ≥ group_size`, woonkamer `yes` / heuristiek / `unknown`; trefwoord-heuristiek (NL/EN/DE, bijv. "woonkamer", "living room", "Wohnzimmer", "open plan") zet `living_room_basis = heuristic` (tests).
  - [ ] CSV-verblijven krijgen `confidence = live` voor prijs als ze een datum-specifieke prijs hebben, anders `estimated`.
  - [ ] Migratie voor de opslag van geïmporteerde verblijven (of opslag als bron-snapshot), getest op echte SQLite.
- **Afhankelijk van**: T-003, T-004
- **Omvang**: M

### T-009b: Verblijf: SerpApi Google Hotels
- **Doel**: live vakantiewoningen met voldoende slaapkamers vinden voor de top-K.
- **Acceptatiecriteria**:
  - [ ] Adapter implementeert `StaySource`: `vacation_rentals=true`, `bedrooms=rooms_min`, `adults=group_size`, check-in/out-data, `currency=EUR`; één zoekopdracht per bestemming.
  - [ ] Resultaten worden gemapt naar `Stay`, door de eis-check gehaald en de beste passende gekozen (test).
  - [ ] Gedeeld SerpApi-quotum: het budget in de pipeline wordt 3 × K (test).
  - [ ] Tests tegen opgenomen fixtures, incl. geen resultaten (terugval op CSV of schatting, gelogd).
- **Afhankelijk van**: T-009a, T-007b
- **Omvang**: M

### T-009c: Verblijf: schatting uit Inside Airbnb
- **Doel**: een prijsschatting als er geen live of CSV-verblijf is, zodat de prijsscore niet leeg blijft.
- **Acceptatiecriteria**:
  - [ ] Per stad een mediaan nachtprijs van listings met `bedrooms ≥ rooms_min` en `accommodates ≥ group_size`, berekend als pure functie (test met kleine fixture-CSV).
  - [ ] Alleen afgeleide statistiek wordt bewaard (snapshot), niet de volledige dataset; downloads via `SourceClient`.
  - [ ] Steden zonder Inside Airbnb-data geven "geen data" (`estimated`, score 5) met uitleg.
  - [ ] Bronvermelding Inside Airbnb (CC BY 4.0) in `ATTRIBUTIONS` (alleen getoond als gebruikt).
- **Afhankelijk van**: T-009a
- **Omvang**: S

### T-010: Activiteiten (Overpass en Wikivoyage) en geocoding
- **Doel**: per bestemming meten hoeveel en hoe gevarieerd er te doen is.
- **Acceptatiecriteria**:
  - [ ] Nominatim-adapter (`Geocoder`): max 1 verzoek/s (test met fake clock), `extratags=1`, resultaten permanent gecachet.
  - [ ] Overpass-adapter: per categorie uit §6 een `out count;`-query in een straal (default 10 km) rond het stadscentrum; één request per stad met meerdere tellingen (test op de gegenereerde query en de parsing).
  - [ ] Wikivoyage-adapter: aantal See/Do-items via de MediaWiki API (test op fixture).
  - [ ] Activiteitenscore volgens §6 met uitleg ("42 musea, 120 bars, 3 escape rooms; 7 van 8 categorieën").
  - [ ] Bronvermelding OSM (ODbL) en Wikivoyage (CC BY-SA) in `ATTRIBUTIONS`.
- **Afhankelijk van**: T-007b
- **Omvang**: M

### T-011: Originaliteit en groepshistorie
- **Doel**: minder bekende en nog niet bezochte bestemmingen hoger waarderen.
- **Acceptatiecriteria**:
  - [ ] Migratie `visit_history` (alleen `city_code`, `city_name`, `visited_on`); integratietest op echte SQLite.
  - [ ] `weekend history add <stad> <datum>` (stad via geocoding/cities-mapping naar `city_code`) en `weekend history list`; ongeldige datum geeft leesbare fout (tests).
  - [ ] Wikimedia Pageviews-adapter: gemiddelde maandelijkse views over de laatste 12 maanden van het Wikipedia-artikel uit het Nominatim-`wikipedia`-tag; User-Agent met `CONTACT_URL` (test op header).
  - [ ] Toerisme-dichtheid uit Overpass (`tourism=*` per km²).
  - [ ] Originaliteitsscore volgens §6, incl. historiestraf (tests per leeftijdsband en maximum).
- **Afhankelijk van**: T-010
- **Omvang**: M

## Mijlpaal 3: Gebruik

### T-012: CLI `weekend rank` met tabel en HTML-rapport
- **Doel**: de volledige trechter in één commando, met een leesbare top-N en een deelbaar rapport.
- **Acceptatiecriteria**:
  - [ ] `weekend rank trips/maart-2027.yaml --top 5 [--offline] [--top-k 12] [--run <id>] [--out report.html]` voert stap 1–7 uit.
  - [ ] Migratie `run_result`; elke run wordt opgeslagen met gebruikte snapshots.
  - [ ] Terminaltabel: rang, stad, totaal, vier scores, betrouwbaarheid per score, prijs p.p., vluchten (tijden, luchthavens, open-jaw), vlaggen.
  - [ ] HTML-rapport via gedeelde Jinja2-templates: top-N met score-opbouw en uitleg, afvallers met reden, quotaverbruik, bronvermelding, links naar boekingssites (geen boeking).
  - [ ] E2E-test: `weekend rank … --offline` op fixture-snapshots geeft twee keer exact dezelfde ranking en hetzelfde rapport (deterministisch, met vaste clock).
  - [ ] Warme-cache-run op fixtures < 30 s (test met ruime marge, geen sleeps).
- **Afhankelijk van**: T-008, T-009b, T-009c, T-011
- **Omvang**: L

### T-013: Web-UI
- **Doel**: dezelfde ranking via een toegankelijk lokaal webformulier.
- **Acceptatiecriteria**:
  - [ ] `weekend serve` start uvicorn op `127.0.0.1` (niet configureerbaar naar `0.0.0.0` zonder expliciete vlag en waarschuwing).
  - [ ] `GET /` formulier met alle `TripConfig`-variabelen (voorgevuld uit een gekozen trip-YAML), `POST /rank` valideert met `TripConfig` en toont fouten per veld plus foutsamenvatting; `GET /runs/{id}` toont resultaten met score-opbouw en bronvermelding.
  - [ ] Live ophalen alleen via vinkje, met het verwachte SerpApi-verbruik ernaast.
  - [ ] Security: TrustedHost, CSRF-token op POST (test: POST zonder token geeft 403), headers CSP/`X-Content-Type-Options`/`Referrer-Policy`/`X-Frame-Options` (test), geen stacktrace op foutpagina (test).
  - [ ] Playwright-e2e (Chromium): formulier invullen, resultaten zien, toetsenbordnavigatie; axe-scan op formulier, foutstatus en resultaten zonder overtredingen (WCAG 2.2 AA tags). Job `e2e` toegevoegd aan `ci`-`needs`.
  - [ ] CSS respecteert `prefers-color-scheme` en `prefers-reduced-motion`; layout werkt op 360 px breed (Playwright-viewporttest).
- **Afhankelijk van**: T-012
- **Omvang**: L

### T-014a: Opt-in-mechanisme en Ryanair-adapter
- **Doel**: onofficiële bronnen veilig en zichtbaar optioneel maken, beginnend met de bron die de kleine luchthavens dekt.
- **Acceptatiecriteria**:
  - [ ] Plug-in-loader voor `plugins/local/` (gitignored, ADR-0004): alleen met `--allow-unofficial` (CLI) of het vinkje (web) wordt er iets geïmporteerd of aangeroepen; getest met een nep-plug-in in `tests/fixtures/plugins/`.
  - [ ] De onofficiële packages staan niet in `pyproject.toml`/`uv.lock`; de README beschrijft de lokale installatie (`uv pip install`) en `pip-audit`.
  - [ ] Waarschuwing op stderr en bovenaan rapport/UI; resultaten gelabeld `unofficial`, betrouwbaarheid hoogstens `cached` (test).
  - [ ] Ryanair-adapter (`RoutePriceSource`, lokale plug-in buiten git; de opdrachtgever krijgt het bestand los aangeleverd) voor EIN, NRN, CRL, DTM, CGN, BRU met eigen limiet (max 30/run, ≥ 2 s tussen verzoeken; fake clock in test).
  - [ ] Falende adapter laat de run niet falen (warning, test).
- **Afhankelijk van**: T-012
- **Omvang**: M

### T-014b: fast-flights- en pyairbnb-adapters
- **Doel**: extra live-vlucht- en verblijfsdekking achter dezelfde opt-in.
- **Acceptatiecriteria**:
  - [ ] `fast_flights` implementeert `LiveFlightSource`, `pyairbnb` implementeert `StaySource`; beide volgen de regels van T-014a (label, limiet, falen zonder run-fout).
  - [ ] Tests tegen opgenomen responses; geen netwerk.
  - [ ] Licentie en onderhoudsstatus van beide packages in de PR.
- **Afhankelijk van**: T-014a
- **Omvang**: M

### T-015: Prijsalarm
- **Doel**: periodiek de shortlist opnieuw prijzen en melden wanneer een prijs daalt.
- **Acceptatiecriteria**:
  - [ ] `weekend watch <trip.yaml> [--threshold-pct 5]` herprijst alleen de top-N van de laatste run (quotabudget vooraf gecontroleerd) en vergelijkt met de vorige run.
  - [ ] Pure vergelijkingsfunctie: daling ≥ drempel per bestemming, nieuwe/verdwenen vluchten (tests).
  - [ ] Melding via console en HTML-rapport; optioneel ntfy als `NTFY_TOPIC` gezet is (`.env.example`, gevalideerd; respx-test op de POST, geen netwerk).
  - [ ] README: instructie voor Windows Taakplanner (wekelijks, `uv run weekend watch … `), incl. `snapshots prune --yes`.
- **Afhankelijk van**: T-012
- **Omvang**: M

### T-016: Echte run voor 19–22 maart 2027
- **Doel**: de tool met echte keys draaien en een top-10-rapport opleveren voor het eerste weekend.
- **Acceptatiecriteria**:
  - [ ] De opdrachtgever heeft de keys zelf in `.env` gezet (agents lezen `.env` niet, AG-3); `weekend airports refresh` en `weekend rank trips/maart-2027.yaml --top 10` gedraaid.
  - [ ] Quotaverbruik ≤ 100% van elke bron, getoond in het rapport; geen `QuotaExceededError` tijdens de run.
  - [ ] Rapport bevat top-10 met scores, betrouwbaarheid, uitleg, afvallers met reden en bronvermelding.
  - [ ] Steekproef: 2 aanbevolen vluchten handmatig gecontroleerd op Google Flights of de site van de maatschappij (tijden, non-stop, prijs voor 10 personen); afwijkingen als issue vastgelegd.
  - [ ] `weekend rank … --offline --run <id>` reproduceert exact dezelfde ranking.
- **Afhankelijk van**: T-013, T-015 (T-014a/b optioneel)
- **Omvang**: S
