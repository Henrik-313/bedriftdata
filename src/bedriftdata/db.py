"""DuckDB-lagringslag: tilkobling, skjema, seed-data og views.

Skjemaet holdes bevisst portabelt mot PostgreSQL (kun TEXT/DATE/TIMESTAMPTZ/
BIGINT/SMALLINT/INTEGER/DOUBLE/BOOLEAN/JSON) siden basen skal migreres dit
i en senere fase. Rå API-svar lagres alltid som JSON ved siden av de
normaliserte kolonnene.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import duckdb

DDL = """
CREATE TABLE IF NOT EXISTS kilde (
    kilde       TEXT PRIMARY KEY,
    navn        TEXT NOT NULL,
    beskrivelse TEXT NOT NULL,
    lisens      TEXT NOT NULL,
    url         TEXT
);

CREATE SEQUENCE IF NOT EXISTS innlasting_seq;
CREATE TABLE IF NOT EXISTS innlasting (
    innlasting_id BIGINT PRIMARY KEY DEFAULT nextval('innlasting_seq'),
    kilde         TEXT NOT NULL,
    startet_tid   TIMESTAMPTZ NOT NULL,
    ferdig_tid    TIMESTAMPTZ,
    status        TEXT NOT NULL,          -- 'kjorer' | 'ok' | 'feilet' | 'avbrutt'
    rader_skrevet BIGINT,
    antall_feil   BIGINT,
    min_dato      DATE,
    max_dato      DATE,
    detaljer      JSON
);

CREATE TABLE IF NOT EXISTS enhet (
    orgnr                 TEXT PRIMARY KEY,
    navn                  TEXT NOT NULL,
    orgform               TEXT NOT NULL,
    naeringskode1         TEXT,
    naering1_beskrivelse  TEXT,
    sektorkode            TEXT,
    kommunenummer         TEXT,
    kommune               TEXT,
    antall_ansatte        INTEGER,
    har_ansatte_reg       BOOLEAN,
    stiftelsesdato        DATE,
    registreringsdato     DATE,
    siste_regnskapsaar    SMALLINT,
    konkurs               BOOLEAN,
    under_avvikling       BOOLEAN,
    under_tvangsavvikling BOOLEAN,
    i_mvaregisteret       BOOLEAN,
    i_foretaksregisteret  BOOLEAN,
    er_i_konsern          BOOLEAN,
    har_hjemmeside        BOOLEAN,
    raa                   JSON NOT NULL,
    hentet_tid            TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS utvalg (
    orgnr     TEXT PRIMARY KEY,
    gruppe    TEXT NOT NULL,
    regel     TEXT NOT NULL,
    valgt_tid TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS hentestatus (
    kilde          TEXT NOT NULL,
    orgnr          TEXT NOT NULL,
    status         TEXT NOT NULL,          -- 'ok' | 'tom' | 'feilet'
    http_status    INTEGER,
    antall_feil    INTEGER NOT NULL DEFAULT 0,
    permanent_feil BOOLEAN NOT NULL DEFAULT FALSE,
    feilmelding    TEXT,
    sist_forsok    TIMESTAMPTZ NOT NULL,
    sist_ok        TIMESTAMPTZ,
    PRIMARY KEY (kilde, orgnr)
);

CREATE TABLE IF NOT EXISTS regnskap (
    orgnr                    TEXT NOT NULL,
    regnskapsaar             SMALLINT NOT NULL,
    regnskapstype            TEXT NOT NULL DEFAULT 'SELSKAP',
    regnskap_id              BIGINT,
    journalnr                TEXT,
    fra_dato                 DATE,
    til_dato                 DATE,
    valuta                   TEXT,
    oppstillingsplan         TEXT,
    avviklingsregnskap       BOOLEAN,
    smaa_foretak             BOOLEAN,
    regnskapsregler          TEXT,
    ikke_revidert            BOOLEAN,
    morselskap               BOOLEAN,
    sum_driftsinntekter      DOUBLE,
    driftsresultat           DOUBLE,
    ordinaert_res_foer_skatt DOUBLE,
    aarsresultat             DOUBLE,
    sum_eiendeler            DOUBLE,
    sum_anleggsmidler        DOUBLE,
    sum_omloepsmidler        DOUBLE,
    sum_egenkapital          DOUBLE,
    sum_innskutt_ek          DOUBLE,
    sum_opptjent_ek          DOUBLE,
    sum_gjeld                DOUBLE,
    sum_kortsiktig_gjeld     DOUBLE,
    sum_langsiktig_gjeld     DOUBLE,
    sum_egenkapital_gjeld    DOUBLE,
    balanseavvik             DOUBLE,
    flagg_balanseavvik       BOOLEAN NOT NULL DEFAULT FALSE,
    raa                      JSON NOT NULL,
    hentet_tid               TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (orgnr, regnskapsaar, regnskapstype)
);

CREATE TABLE IF NOT EXISTS rolle_raa (
    orgnr         TEXT NOT NULL,
    snapshot_dato DATE NOT NULL,
    raa           JSON NOT NULL,
    hentet_tid    TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (orgnr, snapshot_dato)
);

CREATE TABLE IF NOT EXISTS rolle (
    orgnr               TEXT NOT NULL,
    snapshot_dato       DATE NOT NULL,
    rollegruppe         TEXT NOT NULL,
    rolletype           TEXT NOT NULL,
    rekkefolge          INTEGER,
    er_person           BOOLEAN NOT NULL,
    person_navn         TEXT,
    person_foedselsdato DATE,
    person_er_doed      BOOLEAN,
    enhet_orgnr         TEXT,
    enhet_navn          TEXT,
    fratraadt           BOOLEAN,
    hentet_tid          TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS aarsregnskap_aar (
    orgnr        TEXT NOT NULL,
    regnskapsaar SMALLINT NOT NULL,
    hentet_tid   TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (orgnr, regnskapsaar)
);

CREATE TABLE IF NOT EXISTS valutakurs (
    valuta     TEXT NOT NULL,
    dato       DATE NOT NULL,
    kurs_nok   DOUBLE NOT NULL,
    hentet_tid TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (valuta, dato)
);

CREATE TABLE IF NOT EXISTS fylke (
    fylkesnummer TEXT PRIMARY KEY,
    navn         TEXT NOT NULL
);
"""

KILDER = [
    (
        "enheter",
        "Enhetsregisteret",
        "Grunndata om alle registrerte virksomheter (nattlig totaluttrekk fra Brønnøysund)",
        "NLOD 2.0 (Brønnøysundregistrene)",
        "https://data.brreg.no/enhetsregisteret/api/dokumentasjon/no/index.html",
    ),
    (
        "utvalg",
        "Høsteutvalg",
        "Konfigstyrt utvalg av enheter som høstes per selskap (regnskap, roller, årsregnskap)",
        "Avledet av Enhetsregisteret (NLOD 2.0)",
        None,
    ),
    (
        "regnskap",
        "Regnskapsregisteret (åpne data)",
        "Nøkkeltall fra siste innsendte årsregnskap; historikk akkumuleres over kjøringer",
        "NLOD (Brønnøysundregistrene)",
        "https://data.brreg.no/regnskapsregisteret/regnskap/swagger-ui/index.html",
    ),
    (
        "roller",
        "Roller (Enhetsregisteret)",
        "Styre, daglig leder, revisor m.m. – snapshot per dato (API-et har ingen historikk)",
        "NLOD 2.0 (Brønnøysundregistrene)",
        "https://data.brreg.no/enhetsregisteret/api/dokumentasjon/no/index.html",
    ),
    (
        "aarsregnskap_aar",
        "Årsregnskap PDF-årganger",
        "Hvilke årganger av innsendt årsregnskap (PDF) som kan lastes ned gratis per selskap",
        "NLOD (Brønnøysundregistrene)",
        "https://data.brreg.no/regnskapsregisteret/regnskap/swagger-ui/index.html",
    ),
    (
        "valutakurs",
        "Valutakurser (Norges Bank)",
        "Daglige midtkurser i NOK, til normalisering av regnskap i utenlandsk valuta",
        "Fri bruk med kildeangivelse (Norges Bank)",
        "https://data.norges-bank.no",
    ),
]

FYLKER = [
    ("03", "Oslo"),
    ("11", "Rogaland"),
    ("15", "Møre og Romsdal"),
    ("18", "Nordland"),
    ("21", "Svalbard"),
    ("22", "Jan Mayen"),
    ("31", "Østfold"),
    ("32", "Akershus"),
    ("33", "Buskerud"),
    ("34", "Innlandet"),
    ("39", "Vestfold"),
    ("40", "Telemark"),
    ("42", "Agder"),
    ("46", "Vestland"),
    ("50", "Trøndelag"),
    ("55", "Troms"),
    ("56", "Finnmark"),
]

VIEWS = """
CREATE OR REPLACE VIEW v_kildeoversikt AS
WITH siste AS (
    SELECT *
    FROM (
        SELECT *, row_number() OVER (PARTITION BY kilde ORDER BY startet_tid DESC) AS rn
        FROM innlasting
    )
    WHERE rn = 1
),
stat AS (
    SELECT 'enheter' AS kilde,
           (SELECT count(*) FROM enhet) AS rader,
           (SELECT min(registreringsdato) FROM enhet) AS dato_fra,
           (SELECT max(registreringsdato) FROM enhet) AS dato_til
    UNION ALL
    SELECT 'utvalg', (SELECT count(*) FROM utvalg),
           (SELECT cast(min(valgt_tid) AS DATE) FROM utvalg),
           (SELECT cast(max(valgt_tid) AS DATE) FROM utvalg)
    UNION ALL
    SELECT 'regnskap', (SELECT count(*) FROM regnskap),
           (SELECT min(fra_dato) FROM regnskap),
           (SELECT max(til_dato) FROM regnskap)
    UNION ALL
    SELECT 'roller', (SELECT count(*) FROM rolle),
           (SELECT min(snapshot_dato) FROM rolle),
           (SELECT max(snapshot_dato) FROM rolle)
    UNION ALL
    SELECT 'aarsregnskap_aar', (SELECT count(*) FROM aarsregnskap_aar),
           (SELECT make_date(min(regnskapsaar), 1, 1) FROM aarsregnskap_aar),
           (SELECT make_date(max(regnskapsaar), 12, 31) FROM aarsregnskap_aar)
    UNION ALL
    SELECT 'valutakurs', (SELECT count(*) FROM valutakurs),
           (SELECT min(dato) FROM valutakurs),
           (SELECT max(dato) FROM valutakurs)
)
SELECT k.kilde, k.navn, k.beskrivelse, k.lisens, k.url,
       s.rader, s.dato_fra, s.dato_til,
       i.status        AS siste_status,
       i.startet_tid   AS siste_start,
       i.ferdig_tid    AS siste_ferdig,
       i.rader_skrevet AS siste_rader,
       i.antall_feil   AS siste_feil
FROM kilde k
LEFT JOIN stat s USING (kilde)
LEFT JOIN siste i USING (kilde);

CREATE OR REPLACE VIEW v_enhet_fylke AS
SELECT e.*, coalesce(f.navn, 'Ukjent') AS fylke
FROM enhet e
LEFT JOIN fylke f ON substr(e.kommunenummer, 1, 2) = f.fylkesnummer;

CREATE OR REPLACE VIEW v_regnskap_kvalitet AS
SELECT r.*, u.gruppe, u.regel, e.navn, e.naeringskode1, e.orgform
FROM regnskap r
LEFT JOIN utvalg u USING (orgnr)
LEFT JOIN enhet e USING (orgnr);
"""


def koble_til(db_sti: Path | str, read_only: bool = False) -> duckdb.DuckDBPyConnection:
    """Åpner DuckDB-basen. Oppretter foreldremapper ved skrivetilgang."""
    if isinstance(db_sti, str) and db_sti != ":memory:":
        db_sti = Path(db_sti)
    if isinstance(db_sti, Path):
        if not read_only:
            db_sti.parent.mkdir(parents=True, exist_ok=True)
        db_sti = str(db_sti)
    return duckdb.connect(db_sti, read_only=read_only)


def init_skjema(con: duckdb.DuckDBPyConnection) -> None:
    """Oppretter tabeller, seed-data og views. Idempotent."""
    con.execute(DDL)
    con.executemany("INSERT OR REPLACE INTO kilde VALUES (?, ?, ?, ?, ?)", KILDER)
    con.executemany("INSERT OR REPLACE INTO fylke VALUES (?, ?)", FYLKER)
    con.execute(VIEWS)


def sett_inn(
    con: duckdb.DuckDBPyConnection,
    tabell: str,
    rader: list[dict[str, Any]],
    erstatt: bool = True,
) -> int:
    """Setter inn rader (dicts med kolonnenavn som nøkler). Alle rader må ha samme nøkler."""
    if not rader:
        return 0
    kolonner = list(rader[0].keys())
    plassholdere = ", ".join("?" for _ in kolonner)
    verb = "INSERT OR REPLACE" if erstatt else "INSERT"
    sql = f"{verb} INTO {tabell} ({', '.join(kolonner)}) VALUES ({plassholdere})"
    con.executemany(sql, [[rad[kolonne] for kolonne in kolonner] for rad in rader])
    return len(rader)
