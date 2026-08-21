"""Høster siste årsregnskap (JSON) for utvalget. Historikk akkumuleres over kjøringer."""

from __future__ import annotations

import datetime as dt

import duckdb

from bedriftdata import brreg
from bedriftdata.config import Konfig
from bedriftdata.db import sett_inn
from bedriftdata.http import PoliteClient
from bedriftdata.ingest.hosting import kjor_hosting
from bedriftdata.transform import regnskap_til_rad


def _hent_og_skriv(
    con: duckdb.DuckDBPyConnection, client: PoliteClient, orgnr: str
) -> tuple[str, int]:
    regnskaper = brreg.hent_regnskap(client, orgnr)
    if not regnskaper:
        return "tom", 0
    naa = dt.datetime.now(dt.UTC)
    rader = [regnskap_til_rad(orgnr, regnskap, naa) for regnskap in regnskaper]
    rader = [rad for rad in rader if rad["regnskapsaar"] is not None]
    if not rader:
        return "tom", 0
    return "ok", sett_inn(con, "regnskap", rader)


def kjor(
    con: duckdb.DuckDBPyConnection,
    konfig: Konfig,
    limit: int | None = None,
    force: bool = False,
) -> None:
    kjor_hosting(con, konfig, "regnskap", _hent_og_skriv, limit=limit, force=force)
