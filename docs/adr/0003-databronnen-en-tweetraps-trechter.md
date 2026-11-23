# ADR-0003: Databronnen (alleen gratis) en de tweetraps-trechter

- **Status**: voorgesteld
- **Datum**: 2026-11-19
- **Eisen**: brief "Databronnen", NFR Quotum, Transparantie, Licenties, Privacy; SE-1, SE-4, AP-2

## Context
De tool moet directe heen- en terugvluchten voor 10 personen vinden, binnen tijdvensters, vanaf meerdere luchthavens (open-jaw toegestaan), plus verblijf, weer, activiteiten en originaliteit. Alleen gratis API's of gratis tiers mogen. Onderzoek (2026-11-19):
- **Amadeus Self-Service** is per 17-07-2026 gestopt.
- **Kiwi Tequila, Skyscanner, Booking.com Demand, Vrbo**: alleen voor partners.
- **OpenFlights**: routedata uit 2014, onbruikbaar.
- **Transitous** (OV-routering in NL, DE en BE): de voorwaarden vragen dat de afnemende code open source is. Dat is het geval: de repo wordt publiek, met een MIT-licentie (ADR-0006).
  - Extra voorwaarden: niet-commercieel gebruik, een User-Agent met `CONTACT_URL`, een zichtbare bronvermelding, en contact opnemen boven 720 plan-verzoeken per dag.
- Geen enkele gratis bron levert live, betrouwbare groepsprijzen voor álle combinaties. SerpApi (live Google Flights/Hotels) heeft 250 zoekopdrachten per maand, gedeeld.

## Beslissing
**Bronnen**

| Doel | Bron | Quotum/limiet | Cache-TTL |
|---|---|---|---|
| Luchthavens | `data/airports.yaml` (gecontroleerd). Herberekening: ORS-matrix voor de rijtijd, Transitous (`/api/v5/plan`, `arriveBy`) voor de OV-tijd naar alle luchthavens, NS API als controle voor de NL-luchthavens | ORS en NS: gratis keys. Transitous: geen key, ≤ 720 verzoeken per dag | handmatig (`weekend airports refresh`) |
| Routes, indicatieve prijzen | Travelpayouts Data API (`prices_for_dates`, `direct=true`) + statische `airports.json`/`cities.json` | gratis token, rate limit | 24 uur (prijzen), 30 dagen (statisch) |
| Live vluchten | SerpApi Google Flights, **one-way** zoekopdrachten, `departure_id` met alle toegestane luchthavens komma-gescheiden, `stops=1` (non-stop), `adults=N`, `outbound_times` voor het tijdvenster | 250/maand (gedeeld) | 24 uur |
| Verblijf | SerpApi Google Hotels (`vacation_rentals=true`, `bedrooms`), CSV-import, Inside Airbnb-schatting | gedeeld SerpApi-quotum | 24 uur; CSV onbeperkt |
| Weer | Open-Meteo Archive, 30 jaar (1995–2024), ±3 dagen rond de reisdata | fair use | onbeperkt (historische data verandert niet) |
| Activiteiten | OSM Overpass (`out count;` per categorie), Wikivoyage (MediaWiki API) | fair use | 30 dagen |
| Originaliteit | Wikimedia Pageviews, OSM-toerismedichtheid, groepshistorie | User-Agent met `CONTACT_URL` | 30 dagen |
| Geocoding | Nominatim (`extratags=1` voor het `wikipedia`-tag) | 1 verzoek/s | onbeperkt |

**Tweetraps-trechter**
1. *Breed en goedkoop*: Travelpayouts levert voor elke toegestane luchthaven de directe bestemmingen met gecachte prijzen. Per bestemmingsstad wordt een voorlopige score berekend (prijs, plus weer/activiteiten waar al gecachet).
2. *Smal en live*: alleen de top-K (standaard 12) gaat naar SerpApi: 2 vluchtzoekopdrachten (heen en terug, elk over alle luchthavens) en 1 hotelzoekopdracht per bestemming, dus ±36 zoekopdrachten per run. De pipeline berekent dit budget vooraf en weigert te starten (of verkleint K na bevestiging) als het quotum ontoereikend is.

Open-jaw ontstaat vanzelf: heen- en terugvlucht worden los gezocht en vrij gecombineerd. One-way-prijzen kunnen afwijken van retourprijzen; het rapport vermeldt dat.

## Alternatieven
| Alternatief | Waarom niet |
|---|---|
| Alles live via SerpApi | ±13 luchthavens × tientallen bestemmingen ≫ 250 zoekopdrachten per maand. |
| SerpApi retour-zoekopdrachten per luchthavenpaar | Open-jaw vraagt dan veel meer zoekopdrachten; one-way over alle luchthavens tegelijk kost er 2 per bestemming. |
| Betaalde API's (Duffel, Amadeus Enterprise) | Buiten de afspraak "alleen gratis". |

## Gevolgen
- **Positief**: binnen gratis quota; elke score heeft een herleidbare bron en betrouwbaarheid (live/gecachet/geschat).
- **Negatief**: dunne Travelpayouts-dekking op kleine luchthavens (EIN, NRN, FMO, MST, GRQ) kan bestemmingen missen in trap 1; de woonkamer is via geen API te controleren (heuristiek of handmatige vlag). Retourvluchten op 22-03-2027 zijn mogelijk nog niet in verkoop; de tool meldt dat in plaats van de bestemming stil te laten vallen.
- **Licenties**: bronvermelding voor OSM (ODbL), Open-Meteo (CC BY 4.0), Wikimedia/Wikivoyage (CC BY-SA), Inside Airbnb (CC BY 4.0) en openrouteservice staat in UI en rapport. Open-Meteo alleen niet-commercieel: past bij de brief.
- **Privacy**: geen persoonsgegevens naar bronnen; User-Agent bevat alleen de repo-URL (`CONTACT_URL`).
