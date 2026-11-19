# ADR-0005: Web-UI met FastAPI en Jinja2, server-rendered, zonder JS-build

- **Status**: voorgesteld
- **Datum**: 2026-11-19
- **Eisen**: brief "Scope" (lokale web-UI), "Stack", NFR Toegankelijkheid; AP-1, AP-3, SE-4, SE-5, SE-9, OB-4

## Context
Eén organisator wil een formulier met alle trip-variabelen en een resultatenpagina met de opbouw van de scores. De UI draait lokaal. WCAG 2.2 AA is verplicht. Er is geen frontend-expertise of -build nodig in het project.

## Beslissing
- **FastAPI** met **Jinja2**-templates (autoescape aan), statische CSS uit `src/app/web/static/`. Geen JavaScript-framework, geen bundler, geen HTMX in v1: gewone `<form method="post">` met Post/Redirect/Get.
- Dezelfde templates en partials worden gebruikt voor het **HTML-rapport** van de CLI (T-012), zodat score-opbouw en bronvermelding op één plek staan (CQ-7).
- Formulierinvoer wordt gevalideerd met hetzelfde pydantic-model als de trip-YAML (`TripConfig`); fouten worden per veld getoond met `aria-describedby` en een foutsamenvatting bovenaan.
- **Security**: uvicorn bindt alleen op `127.0.0.1`; `TrustedHostMiddleware` (`localhost`, `127.0.0.1`) tegen DNS-rebinding; CSRF-token (double-submit) op elke POST, omdat een externe website anders via de browser runs kan starten die quotum kosten; headers `Content-Security-Policy: default-src 'self'`, `X-Content-Type-Options`, `Referrer-Policy: no-referrer`, `X-Frame-Options: DENY`. Geen CORS. Alle routes zijn expliciet; onbekende paden geven 404 (SE-5: alleen lokale toegang, geen accounts nodig – single-user, zie brief).
- **Live runs** in de UI zijn opt-in (vinkje "live gegevens ophalen", met het verwachte quotaverbruik ernaast). Standaard rekent de UI met cache en snapshots, zodat een request binnen 30 s klaar is.
- **Toegankelijkheid**: semantische HTML, zichtbare focus, contrast ≥ 4.5:1, tabellen met `<th scope>`, `prefers-color-scheme` en `prefers-reduced-motion` in CSS. Playwright + axe in de e2e-tests (AP-1).

## Alternatieven
| Alternatief | Waarom niet |
|---|---|
| React/Vue SPA | JS-build, extra toolchain, extra tests en audit; geen voordeel voor één formulier en één resultatenpagina. |
| HTMX | Prettig voor voortgang, maar niet nodig in v1; kan later zonder build worden toegevoegd. |
| Streamlit/Gradio | Beperkte controle over toegankelijkheid en HTML-semantiek. |

## Gevolgen
- **Positief**: één taal, geen JS-build, goed toetsbaar met `TestClient` en Playwright.
- **Negatief**: geen voortgangsweergave tijdens een koude live run; de UI verwijst daarvoor naar de CLI.
- **Vervolgacties**: Playwright-browsers worden in CI geïnstalleerd (`playwright install --with-deps chromium`), wat de CI-duur verhoogt (CI-4 bewaken).
