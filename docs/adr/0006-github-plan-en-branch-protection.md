# ADR-0006: Publieke repo en lokale werkwijze tot de eerste push

- **Status**: geaccepteerd
- **Datum**: 2026-11-19
- **Eisen**: VC-1, VC-2, VC-3 (MUST), SE-2 (MUST), SE-7 (SHOULD), AG-5

## Context
- **Wens van de opdrachtgever:** geen betaald GitHub-account.
- **Gevolg voor een private repo:** op GitHub Free werkt branch protection niet (VC-3). Secret scanning en push protection werken daar ook niet (SE-2). Dat zijn allebei MUST-eisen.
- **Wat een publieke repo gratis biedt:** branch protection, secret scanning, push protection en CodeQL.
- **Werkwijze voorlopig:** de opdrachtgever heeft daarnaast bepaald dat alles **voorlopig lokaal** blijft. Er gaat niets naar GitHub tot hij daar opnieuw akkoord op geeft.

## Beslissing
1. **Publieke repo op GitHub Free**, met een MIT-licentie, zodra de opdrachtgever akkoord geeft op de eerste push.
   - Bij het aanmaken stellen we in: branch protection op `main` volgens VC-3 (PR verplicht, required check `ci`, geen force-push, geen verwijdering), secret scanning met push protection, en CodeQL.
2. **Wat nooit in de repo komt:**
   - echte reisplannen (`trips/local/`);
   - groepshistorie, snapshots en de database (`var/`);
   - onofficiële adapters (`plugins/local/`, zie ADR-0004).

   Deze mappen staan in `.gitignore`. Er wordt alleen een voorbeeld-trip gecommit.
3. **Lokale werkwijze tot de eerste push:**
   - Elke taak krijgt een eigen branch en wordt lokaal gereviewd door de `code-reviewer`- en `security-auditor`-agent.
   - Daarna volgen de controle van de projectleider en een squash-merge naar `main` met een Conventional-Commit-bericht.
   - Ter compensatie van de branch protection die er lokaal nog niet is:
     - de pre-commit-hook `no-commit-to-branch` (main) weigert commits direct op `main`;
     - gitleaks draait in pre-commit;
     - de volledige controle (format, lint, typecheck, tests met coverage, build, pip-audit) draait lokaal vóór elke merge.

## Alternatieven
| Alternatief | Waarom niet |
|---|---|
| Private repo met GitHub Pro | De opdrachtgever wil niet betalen. |
| Private repo op Free | Branch protection en push protection zijn niet af te dwingen: een afwijking van een MUST. |
| Andere host (GitLab, Codeberg) | Botst met VC-1 (GitHub). |

## Gevolgen
- **Positief:**
  - Na de eerste push zijn VC-3, SE-2 en SE-7 volledig gedekt zonder kosten.
  - Transitous mag nu gebruikt worden, omdat de code open source is (ADR-0003).
- **Negatief:**
  - De code is openbaar. De onofficiële adapters horen daarom niet in de repo.
  - Zolang alles lokaal blijft, hangt VC-3 af van de pre-commit-hook en van discipline. Die hook kan omzeild worden met `--no-verify`, en dat is verboden (AG-2).
- **Vervolgacties:**
  - Bij akkoord op de eerste push: `gh repo create --public`, daarna branch protection en de security-instellingen via `gh api`, en een eerste PR waarop de `ci`-check groen moet worden.
  - De GitHub-workflows (ci, codeql, release-please) worden pas dan voor het eerst echt uitgevoerd.
