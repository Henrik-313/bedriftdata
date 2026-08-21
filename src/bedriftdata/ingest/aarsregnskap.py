"""Høster metadata om tilgjengelige årsregnskap-PDF-er (kun årslister, ikke PDF-ene)."""

from __future__ import annotations

import datetime as dt

import duckdb

from bedriftdata import brreg
from bedriftdata.config import Konfig
from bedriftdata.db import sett_inn
from bedriftdata.http import PoliteClient
from bedriftdata.ingest.hosting import kjor_hosting


def _hent_og_skriv(
    con: duckdb.DuckDBPyConnection, client: PoliteClient, orgnr: str
) -> tuple[str, int]:
    aar_liste = brreg.hent_aarsregnskap_aar(client, orgnr)
    gyldige = [int(aar) for aar in aar_liste or [] if str(aar).isdigit()]
    if not gyldige:
        return "tom", 0

    naa = dt.datetime.now(dt.UTC)
    # Listen er autoritativ per oppslag -> erstatt alt for enheten
    con.execute("DELETE FROM aarsregnskap_aar WHERE orgnr = ?", [orgnr])
    rader = [{"orgnr": orgnr, "regnskapsaar": aar, "hentet_tid": naa} for aar in gyldige]
    return "ok", sett_inn(con, "aarsregnskap_aar", rader, erstatt=False)


def kjor(
    con: duckdb.DuckDBPyConnection,
    konfig: Konfig,
    limit: int | None = None,
    force: bool = False,
) -> None:
    kjor_hosting(con, konfig, "aarsregnskap_aar", _hent_og_skriv, limit=limit, force=force)
