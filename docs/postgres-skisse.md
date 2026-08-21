# Skisse: datamodell og innlastingsstrategi for PostgreSQL

Utkast basert på utforskningen – justeres når vi skalerer opp.

> **Status august 2026:** Dashbord-fasen bruker DuckDB (`data/bedriftdata.duckdb`)
> med et skjema som følger denne skissen tett (se `src/bedriftdata/db.py` for
> fasiten – bl.a. er `hentestatus`- og `utvalg`-tabeller kommet til, og
> roller lagres som daterte snapshots i stedet for SCD2). Migreringen til
> PostgreSQL blir i hovedsak `CREATE TABLE` + `COPY`, siden typene er
> holdt portable og rå-JSON ligger i basen.

## Prinsipper

1. **Rådata + modellerte tabeller.** API-svar lagres som `jsonb` i råtabeller
   (med hentetidspunkt), og nøkkeltall normaliseres til analysetabeller.
   Da kan modellene endres uten å hente alt på nytt.
2. **Historikk fra dag én.** Åpne API-er gir kun nåsituasjon (roller) eller
   siste år (regnskap). Verdien av databasen kommer fra å snapshotte over tid.
3. **Bulk først, deretter endringsstrøm.** Grunnlast fra nattlige bulk-filer,
   vedlikehold via oppdaterings-API-ene med lagret markør (`oppdateringsid`).
4. **NLOD-attribusjon:** «Inneholder data under Norsk lisens for offentlige data
   (NLOD) tilgjengeliggjort av Brønnøysundregistrene» ved publisering.

## Tabeller (utkast)

```sql
-- Grunndata fra Enhetsregisteret
create table enhet (
    orgnr           text primary key,
    navn            text not null,
    orgform         text not null,
    naeringskode1   text,
    sektorkode      text,
    kommunenummer   text,
    antall_ansatte  integer,
    stiftelsesdato  date,
    registrert_dato date,
    konkurs         boolean,
    under_avvikling boolean,
    slettedato      date,
    siste_regnskapsaar smallint,
    raa             jsonb not null,
    hentet_tid      timestamptz not null
);

create table underenhet (
    orgnr        text primary key,
    hovedenhet   text references enhet(orgnr),
    -- adresse, næringskode, ansatte per lokasjon
    raa          jsonb not null,
    hentet_tid   timestamptz not null
);

-- Regnskap: én rad per (orgnr, regnskapsår, type). Bygger historikk over tid.
create table regnskap (
    orgnr            text not null,
    regnskapsaar     smallint not null,
    regnskapstype    text not null default 'SELSKAP',
    fra_dato         date,
    til_dato         date,
    valuta           text,
    oppstillingsplan text,
    smaa_foretak     boolean,
    ikke_revidert    boolean,
    sum_driftsinntekter numeric,
    driftsresultat      numeric,
    aarsresultat        numeric,
    sum_eiendeler       numeric,
    sum_egenkapital     numeric,
    sum_gjeld           numeric,
    raa              jsonb not null,
    hentet_tid       timestamptz not null,
    primary key (orgnr, regnskapsaar, regnskapstype)
);

-- Årsrapport-PDF-er: metadata i basen, filene på disk/objektlager
create table aarsregnskap_pdf (
    orgnr        text not null,
    regnskapsaar smallint not null,
    filsti       text not null,
    antall_bytes integer,
    lastet_tid   timestamptz not null,
    primary key (orgnr, regnskapsaar)
);

-- Roller: snapshot-modell med gyldighetsintervall (SCD2)
create table rolle (
    orgnr        text not null,
    rollegruppe  text not null,          -- DAGL, STYR, REVI, ...
    rolletype    text not null,
    person_navn  text,
    person_foedselsdato date,
    rolleenhet_orgnr text,               -- når rollen holdes av juridisk enhet
    gyldig_fra   timestamptz not null,
    gyldig_til   timestamptz             -- null = gjeldende
);

-- Børsnoterte selskaper: manuelt kvalitetssikret kobling
create table utsteder (
    ticker  text primary key,            -- f.eks. EQNR
    isin    text,
    navn    text not null,
    orgnr   text references enhet(orgnr), -- null for utenlandskregistrerte
    merknad text
);

create table kurs (
    ticker  text not null references utsteder(ticker),
    dato    date not null,
    open    numeric, high numeric, low numeric, close numeric,
    volum   bigint,
    kilde   text not null,
    primary key (ticker, dato)
);

-- Synk-tilstand for endringsstrømmene
create table synk_markoer (
    kilde           text primary key,    -- 'enheter', 'underenheter', 'roller'
    oppdateringsid  bigint not null,
    oppdatert_tid   timestamptz not null
);
```

## Innlastingsstrategi

| Datasett | Grunnlast | Vedlikehold |
|---|---|---|
| Enheter/underenheter | Nattlig bulk-fil (gzip JSON) | `oppdateringer`-API med id-markør |
| Regnskap (JSON) | Batch over alle regnskapspliktige (~450k kall, ratebegrenset over noen netter) | Nye innsendinger: re-hent når `sisteInnsendteAarsregnskap` endres i endringsstrømmen |
| Årsrapport-PDF | Ved behov / prioriterte utvalg (lagringstungt) | Årlig |
| Roller | `totalbestand`-fil | `oppdateringer/roller` + SCD2-lukking |
| Kurser | yfinance (utforskning) → vurder lisensiert kilde | Daglig jobb |

## Åpne spørsmål til neste fase

- OCR-pipeline for historiske regnskaps-PDF-er: verdt kostnaden, eller holder
  det å bygge historikk fremover + kjøpe historikk ved konkret behov?
- Aksjonærregisteret: bestille årlig dump fra Skatteetaten og modellere eierskap?
- Konsernstrukturer: `erIKonsern`-flagget finnes, men konsernrelasjoner må ev.
  utledes fra rolledata/regnskap (morselskap-feltet) eller kjøpes.
