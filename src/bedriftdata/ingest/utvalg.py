"""Bygger høsteutvalget fra enhet-tabellen etter reglene i config.toml.

Rent SQL – ingen API-kall. Deterministisk trekking med ORDER BY hash(orgnr),
så samme config gir samme utvalg (og en utvidet config gir et supersett).
"""

from __future__ import annotations

import datetime as dt

import duckdb

from bedriftdata.config import Konfig, UtvalgsRegel
from bedriftdata.ingest.runlog import Innlasting


def _regel_sql(regel: UtvalgsRegel) -> tuple[str, list]:
    """SELECT for én regel. Ansattfiltre tolkes mot coalesce(antall_ansatte, 0)."""
    betingelser = ["orgform = ?"]
    params: list = [regel.orgform]
    if regel.ansatte_min is not None:
        betingelser.append("coalesce(antall_ansatte, 0) >= ?")
        params.append(regel.ansatte_min)
    if regel.ansatte_max is not None:
        betingelser.append("coalesce(antall_ansatte, 0) <= ?")
        params.append(regel.ansatte_max)
    sql = f"SELECT orgnr FROM enhet WHERE {' AND '.join(betingelser)} ORDER BY hash(orgnr)"
    if regel.antall is not None:
        sql += " LIMIT ?"
        params.append(regel.antall)
    return sql, params


def kjor(con: duckdb.DuckDBPyConnection, konfig: Konfig) -> None:
    """Erstatter utvalg-tabellen. Krever at enhet-tabellen er lastet."""
    antall_enheter = con.execute("SELECT count(*) FROM enhet").fetchone()[0]
    if antall_enheter == 0:
        raise SystemExit("enhet-tabellen er tom – kjør `bedriftdata enheter` først")

    detaljer = {regel.navn: (regel.antall or "alle") for regel in konfig.utvalgsregler}
    with Innlasting(con, "utvalg", detaljer) as logg:
        valgt_tid = dt.datetime.now(dt.UTC)
        con.execute("BEGIN")
        try:
            con.execute("DELETE FROM utvalg")
            for regel in konfig.utvalgsregler:
                sql, params = _regel_sql(regel)
                # OR IGNORE: en enhet som treffer flere regler beholder første regel
                con.execute(
                    f"INSERT OR IGNORE INTO utvalg SELECT orgnr, ?, ?, ? FROM ({sql})",
                    [regel.navn, regel.navn, valgt_tid, *params],
                )
            con.execute("COMMIT")
        except Exception:
            con.execute("ROLLBACK")
            raise

        per_regel = con.execute(
            "SELECT regel, count(*) FROM utvalg GROUP BY regel ORDER BY regel"
        ).fetchall()
        totalt = sum(antall for _, antall in per_regel)
        logg.registrer(rader=totalt)
        logg.sett_datospenn(valgt_tid.date(), valgt_tid.date())
        for regel, antall in per_regel:
            print(f"  {regel}: {antall:,}")
        print(f"Utvalg bygget: {totalt:,} enheter")
