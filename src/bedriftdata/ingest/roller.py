"""Høster roller for utvalget som snapshot per dato (API-et har ingen historikk)."""

from __future__ import annotations

import datetime as dt
import json

import duckdb

from bedriftdata import brreg
from bedriftdata.config import Konfig
from bedriftdata.db import sett_inn
from bedriftdata.http import PoliteClient
from bedriftdata.ingest.hosting import kjor_hosting
from bedriftdata.transform import roller_til_rader


def _hent_og_skriv(
    con: duckdb.DuckDBPyConnection, client: PoliteClient, orgnr: str
) -> tuple[str, int]:
    svar = brreg.hent_roller(client, orgnr)
    if not svar or not svar.get("rollegrupper"):
        return "tom", 0

    naa = dt.datetime.now(dt.UTC)
    snapshot_dato = naa.date()
    rader = roller_til_rader(orgnr, svar, snapshot_dato, naa)

    # Samme dag lastes på nytt -> erstatt snapshotet (idempotent per dag)
    con.execute("DELETE FROM rolle WHERE orgnr = ? AND snapshot_dato = ?", [orgnr, snapshot_dato])
    con.execute(
        "DELETE FROM rolle_raa WHERE orgnr = ? AND snapshot_dato = ?", [orgnr, snapshot_dato]
    )
    sett_inn(
        con,
        "rolle_raa",
        [
            {
                "orgnr": orgnr,
                "snapshot_dato": snapshot_dato,
                "raa": json.dumps(svar, ensure_ascii=False),
                "hentet_tid": naa,
            }
        ],
        erstatt=False,
    )
    return "ok", sett_inn(con, "rolle", rader, erstatt=False)


def kjor(
    con: duckdb.DuckDBPyConnection,
    konfig: Konfig,
    limit: int | None = None,
    force: bool = False,
) -> None:
    kjor_hosting(con, konfig, "roller", _hent_og_skriv, limit=limit, force=force)
