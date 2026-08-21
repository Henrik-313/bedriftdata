# bedriftdata

Innsamling av åpne data om norske bedrifter til senere analyser, med et
Streamlit-dashbord som viser hva som er hentet og deskriptiv statistikk
per kilde. Lagring i DuckDB (én fil) i denne fasen; PostgreSQL er planen
ved oppskalering, og skjemaet er holdt portabelt (rå JSON + normaliserte
kolonner).

Kilder i denne fasen (kun åpent lisensiert, kommersiell-vennlig data):
Enhetsregisteret (bulk + endringsflagg), Regnskapsregisteret (åpne
nøkkeltall + metadata om gratis PDF-årsregnskap), roller, og valutakurser
fra Norges Bank. Kartleggingen bak kildevalgene ligger i [`docs/`](docs/).

## Oppsett

Krever [uv](https://docs.astral.sh/uv/). Python 3.13 og avhengigheter
installeres automatisk:

```bash
uv sync
```

## Innlasting

```bash
uv run bedriftdata alt
```

kjører alle jobbene i riktig rekkefølge (~30–45 min første gang, hvorav
bulk-nedlastingen av Enhetsregisteret er mesteparten). Jobbene kan også
kjøres enkeltvis:

| Kommando | Hva den gjør | Varighet |
|---|---|---|
| `bedriftdata init` | oppretter/oppgraderer skjemaet | sekunder |
| `bedriftdata enheter` | hele Enhetsregisteret fra nattlig bulk-fil (~1,17 mill.) | ~10 min |
| `bedriftdata utvalg` | bygger høsteutvalget fra `config.toml` (~2 000) | sekunder |
| `bedriftdata regnskap` | siste årsregnskap (JSON) for utvalget | ~10 min |
| `bedriftdata roller` | roller som snapshot per dato | ~10 min |
| `bedriftdata aarsregnskap` | metadata om gratis PDF-årganger | ~10 min |
| `bedriftdata valutakurser` | daglige kurser fra Norges Bank | sekunder |
| `bedriftdata status` | kildeoversikt, hentestatus og siste kjøringer | sekunder |

Nyttige flagg: `--limit N` (røyktest på få selskaper), `--force` (ignorer
friskhetsvindu og permanente feil), `enheter --gjenbruk-fil` (ikke last ned
bulk-filen på nytt).

Kjøringene er **idempotente og gjenopptakbare**: per-selskap-jobbene hopper
over alt som er hentet siste 30 dager (`friskhet_dager` i config), og
regnskapshistorikk akkumuleres over årlige kjøringer. Banker og
forsikringsforetak gir vedvarende feil i det åpne regnskaps-API-et og
merkes permanent etter første forsøk – de re-forsøkes ikke.

Utvid datagrunnlaget ved å justere `[[utvalg.regler]]` i
[`config.toml`](config.toml) og kjøre `utvalg` + høstejobbene på nytt.

## Dashbord

```bash
uv run streamlit run app/dashboard.py
```

Seks sider: **Oversikt** (kildekatalog med status, radantall, datospenn og
kjøringslogg), **Enhetsregisteret**, **Regnskap**, **Roller**,
**Årsregnskap (PDF)** (inkl. nedlasting av enkelt-PDF-er på forespørsel) og
**Valutakurser**.

**Én skriver om gangen:** DuckDB tillater ikke innlasting mens dashbordet
har basen åpen. Stopp dashbordet (Ctrl+C) før du kjører `bedriftdata`-
kommandoer; begge sider gir tydelig beskjed hvis basen er låst.

## Lisens og personvern

- Data fra Brønnøysundregistrene er underlagt **NLOD**: «Inneholder data
  under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av
  Brønnøysundregistrene.» Valutakurser: kilde Norges Bank.
- **Rolledata inneholder personopplysninger** (navn og fødselsdato).
  Basen ligger i `data/` (gitignorert) og skal ikke deles eller
  publiseres; dashbordet viser kun aggregater.
- Aksjekurser er bevisst utelatt: gratis kilder (Yahoo/yfinance) er kun
  lisensiert for personlig bruk. `explore/05_aksjekurs.py` kan fortsatt
  kjøres med `uv sync --group explore`.

## Struktur

```
config.toml          utvalgsregler, friskhet, valutaer, db-sti
src/bedriftdata/     gjenbrukbar kode (HTTP-klient, API-wrappere, skjema, transformasjoner)
src/bedriftdata/ingest/  innlastingsjobbene bak bedriftdata-CLI-en
app/                 Streamlit-dashbordet (dashboard.py + sider/)
tests/               pytest (syntetiske fixtures – aldri ekte persondata)
explore/             utforskningsskriptene fra kartleggingsfasen (arkiv)
docs/                kildekartlegging, kvalitetsvurdering og PostgreSQL-skisse
data/                database og rådata (gitignorert, reproduserbart)
```

## Verktøy

- `uv run pytest` – tester
- `uv run ruff check .` / `uv run ruff format .` – lint og formatering
