"""Laster daglige valutakurser fra Norges Bank inn i valutakurs-tabellen."""

from __future__ import annotations

import datetime as dt

import duckdb

from bedriftdata.config import Konfig
from bedriftdata.http import PoliteClient
from bedriftdata.ingest.runlog import Innlasting
from bedriftdata.norgesbank import hent_valutakurser


def kjor(con: duckdb.DuckDBPyConnection, konfig: Konfig) -> None:
    detaljer = {"valutaer": konfig.valutaer, "start_aar": konfig.valuta_start_aar}
    with Innlasting(con, "valutakurs", detaljer) as logg:
        with PoliteClient(requests_per_second=konfig.requests_per_second) as client:
            kurser = hent_valutakurser(client, konfig.valutaer, konfig.valuta_start_aar)

        con.register("kurser_df", kurser)
        con.execute(
            "INSERT OR REPLACE INTO valutakurs"
            " SELECT valuta, CAST(dato AS DATE), kurs_nok, ? FROM kurser_df",
            [dt.datetime.now(dt.UTC)],
        )
        con.unregister("kurser_df")

        min_dato, max_dato = con.execute("SELECT min(dato), max(dato) FROM valutakurs").fetchone()
        logg.registrer(rader=len(kurser))
        logg.sett_datospenn(min_dato, max_dato)
        print(f"  {len(kurser):,} kurser lastet ({min_dato} til {max_dato})")
