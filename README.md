# bedriftdata

Innsamling av data om norske bedrifter til bruk i senere analyser: regnskapstall,
registerdata, kunngjøringer, aksjekurser m.m.

**Status: utforskningsfase.** Målet nå er å kartlegge hvilke data som er åpent
tilgjengelige og hvilken kvalitet de har, før pipelinen skaleres opp mot en
PostgreSQL-database. Funnene er dokumentert i [`docs/`](docs/):

- [`docs/datakilder.md`](docs/datakilder.md) – kartlegging av kilder: API-er, lisenser, begrensninger
- [`docs/kvalitetsvurdering.md`](docs/kvalitetsvurdering.md) – målt datakvalitet på utvalg
- [`docs/postgres-skisse.md`](docs/postgres-skisse.md) – utkast til datamodell og innlastingsstrategi

## Oppsett

Krever [uv](https://docs.astral.sh/uv/). Python 3.13 og avhengigheter installeres automatisk:

```bash
uv sync
```

## Utforskningsskript

Skriptene i [`explore/`](explore/) er nummerert og kjøres i rekkefølge
(01 lager utvalget de andre bruker). Alle skriver resultater til `data/`
(ikke versjonert) og oppsummeringer til terminalen.

```bash
uv run python explore/01_enhetsregisteret.py
```

| Skript | Hva det undersøker |
|---|---|
| `00_roketest.py` | Rask verifisering av endepunkter og svarstruktur |
| `01_enhetsregisteret.py` | Bestand, feltdekning og stratifisert utvalg fra Enhetsregisteret |
| `02_regnskap.py` | Det åpne regnskaps-API-et: treffrate, ferskhet, konsistens |
| `03_roller.py` | Roller (styre, daglig leder, revisor) |
| `04_oppdateringer.py` | Endringsstrømmen – grunnlag for inkrementell synk |
| `05_aksjekurs.py` | Kursdata via yfinance + kobling ticker ↔ orgnr |
| `06_proff_robots.py` | Hva Proff.no tillater av automatisert tilgang |

## Struktur

```
src/bedriftdata/   gjenbrukbar kode (HTTP-klient, API-wrappere)
explore/           utforskningsskript (engangsanalyser)
docs/              funn og beslutningsgrunnlag
data/              nedlastede rådata og utvalg (gitignorert, reproduserbart)
```

## Verktøy

- `uv run ruff check .` – lint
- `uv run ruff format .` – formatering
