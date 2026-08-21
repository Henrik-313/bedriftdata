"""Laster hele Enhetsregisteret fra det nattlige totaluttrekket (gzip JSON).

Strategi: last ned filen strømmende, la DuckDB lese den direkte med
read_json_objects (gir hvert objekt som ren JSON uten skjemainferens – robust
mot sjeldne felter), og erstatt enhet-tabellen i én transaksjon. Feltplukkingen
skjer i SQL med TRY_CAST så enkeltrader med rare verdier ikke velter lasten.
"""

from __future__ import annotations

import datetime as dt

import duckdb

from bedriftdata import brreg
from bedriftdata.config import Konfig
from bedriftdata.http import PoliteClient
from bedriftdata.ingest.runlog import Innlasting
from bedriftdata.utils import DATA_RAW

# j er hele enhets-objektet som JSON; rekkefølgen matcher enhet-tabellen.
ENHET_SELECT = """
SELECT
    j->>'$.organisasjonsnummer'                                   AS orgnr,
    j->>'$.navn'                                                  AS navn,
    j->>'$.organisasjonsform.kode'                                AS orgform,
    j->>'$.naeringskode1.kode'                                    AS naeringskode1,
    j->>'$.naeringskode1.beskrivelse'                             AS naering1_beskrivelse,
    j->>'$.institusjonellSektorkode.kode'                         AS sektorkode,
    j->>'$.forretningsadresse.kommunenummer'                      AS kommunenummer,
    j->>'$.forretningsadresse.kommune'                            AS kommune,
    TRY_CAST(j->>'$.antallAnsatte' AS INTEGER)                    AS antall_ansatte,
    TRY_CAST(j->>'$.harRegistrertAntallAnsatte' AS BOOLEAN)       AS har_ansatte_reg,
    TRY_CAST(j->>'$.stiftelsesdato' AS DATE)                      AS stiftelsesdato,
    TRY_CAST(j->>'$.registreringsdatoEnhetsregisteret' AS DATE)   AS registreringsdato,
    TRY_CAST(j->>'$.sisteInnsendteAarsregnskap' AS SMALLINT)      AS siste_regnskapsaar,
    TRY_CAST(j->>'$.konkurs' AS BOOLEAN)                          AS konkurs,
    TRY_CAST(j->>'$.underAvvikling' AS BOOLEAN)                   AS under_avvikling,
    TRY_CAST(j->>'$.underTvangsavviklingEllerTvangsopplosning' AS BOOLEAN)
                                                                  AS under_tvangsavvikling,
    TRY_CAST(j->>'$.registrertIMvaregisteret' AS BOOLEAN)         AS i_mvaregisteret,
    TRY_CAST(j->>'$.registrertIForetaksregisteret' AS BOOLEAN)    AS i_foretaksregisteret,
    TRY_CAST(j->>'$.erIKonsern' AS BOOLEAN)                       AS er_i_konsern,
    (j->'$.hjemmeside') IS NOT NULL                               AS har_hjemmeside,
    j                                                             AS raa,
    ?                                                             AS hentet_tid
"""

BULK_FIL = DATA_RAW / "enheter_lastned.json.gz"


def kjor(
    con: duckdb.DuckDBPyConnection, konfig: Konfig, hopp_over_nedlasting: bool = False
) -> None:
    """Laster ned bulk-filen og erstatter enhet-tabellen."""
    with Innlasting(con, "enheter", {"url": brreg.ENHETER_BULK_URL}) as logg:
        if not (hopp_over_nedlasting and BULK_FIL.exists()):
            print(f"Laster ned {brreg.ENHETER_BULK_URL} ...")
            with PoliteClient(requests_per_second=konfig.requests_per_second) as client:
                byte = client.last_ned_fil(brreg.ENHETER_BULK_URL, BULK_FIL)
            print(f"  {byte / 1_048_576:,.0f} MB lastet ned")
        else:
            print(f"Gjenbruker eksisterende {BULK_FIL.name}")

        sti = BULK_FIL.as_posix().replace("'", "''")
        con.execute("SET preserve_insertion_order = false")
        print("Leser bulk-filen inn i enhet-tabellen (noen minutter) ...")
        con.execute("BEGIN")
        try:
            con.execute("DELETE FROM enhet")
            con.execute(
                f"INSERT INTO enhet {ENHET_SELECT}"
                f" FROM read_json_objects('{sti}', format='auto') AS t(j)",
                [dt.datetime.now(dt.UTC)],
            )
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise

        antall = con.execute("SELECT count(*) FROM enhet").fetchone()[0]
        min_dato, max_dato = con.execute(
            "SELECT min(registreringsdato), max(registreringsdato) FROM enhet"
        ).fetchone()
        logg.registrer(rader=antall)
        logg.sett_datospenn(min_dato, max_dato)
        print(f"  {antall:,} enheter lastet (registrert {min_dato} til {max_dato})")
