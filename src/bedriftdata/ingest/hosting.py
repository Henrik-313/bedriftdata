"""Felles motor for per-orgnr-høsting (regnskap, roller, årsregnskap-metadata).

Håndterer utvalg av hvilke orgnr som skal hentes (resume via hentestatus),
feilklassifisering (inkl. permanent feil for finansforetak i regnskaps-API-et)
og kjøringslogg. Selve API-kallet og radskrivingen leveres av hver jobb.
"""

from __future__ import annotations

import datetime as dt
from collections.abc import Callable

import duckdb
import httpx
from tqdm import tqdm

from bedriftdata.config import Konfig
from bedriftdata.http import PoliteClient
from bedriftdata.ingest.runlog import Innlasting

# En jobb returnerer (status, antall_rader): status 'ok' eller 'tom'.
HosteFunksjon = Callable[[duckdb.DuckDBPyConnection, PoliteClient, str], tuple[str, int]]

FINANS_MELDING = "finansforetak: oppstillingsplan støttes ikke av det åpne regnskaps-API-et"
MAKS_FEILEDE_KJORINGER = 3


def _velg_orgnr(
    con: duckdb.DuckDBPyConnection,
    kilde: str,
    friskhet_dager: int,
    force: bool,
    limit: int | None,
) -> list[tuple[str, str | None]]:
    """Orgnr fra utvalget som skal (re)hentes nå, med næringskode for feilklassifisering."""
    cutoff = dt.datetime.now(dt.UTC) - dt.timedelta(days=friskhet_dager)
    if force:
        betingelse = "TRUE"
        params: list = [kilde]
    else:
        betingelse = (
            "h.orgnr IS NULL OR (NOT h.permanent_feil"
            " AND NOT (h.status IN ('ok', 'tom') AND h.sist_forsok >= ?))"
        )
        params = [kilde, cutoff]
    sql = f"""
        SELECT u.orgnr, e.naeringskode1
        FROM utvalg u
        LEFT JOIN hentestatus h ON h.kilde = ? AND h.orgnr = u.orgnr
        LEFT JOIN enhet e ON e.orgnr = u.orgnr
        WHERE {betingelse}
        ORDER BY u.orgnr
    """
    if limit is not None:
        sql += " LIMIT ?"
        params.append(limit)
    return con.execute(sql, params).fetchall()


def _oppdater_hentestatus(
    con: duckdb.DuckDBPyConnection,
    kilde: str,
    orgnr: str,
    status: str,
    http_status: int | None,
    feilmelding: str | None,
    naeringskode: str | None,
) -> bool:
    """Skriver hentestatus-raden. Returnerer True hvis feilen ble markert permanent."""
    naa = dt.datetime.now(dt.UTC)
    forrige = con.execute(
        "SELECT antall_feil, sist_ok FROM hentestatus WHERE kilde = ? AND orgnr = ?",
        [kilde, orgnr],
    ).fetchone()
    antall_feil, sist_ok = forrige if forrige else (0, None)

    permanent = False
    if status == "feilet":
        antall_feil += 1
        er_finans = (naeringskode or "")[:2] in ("64", "65")
        if kilde == "regnskap" and http_status == 500 and er_finans:
            permanent = True
            feilmelding = FINANS_MELDING
        elif antall_feil >= MAKS_FEILEDE_KJORINGER:
            permanent = True
    else:
        antall_feil = 0
        sist_ok = naa

    con.execute(
        "INSERT OR REPLACE INTO hentestatus VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        [kilde, orgnr, status, http_status, antall_feil, permanent, feilmelding, naa, sist_ok],
    )
    return permanent


def kjor_hosting(
    con: duckdb.DuckDBPyConnection,
    konfig: Konfig,
    kilde: str,
    jobb: HosteFunksjon,
    limit: int | None = None,
    force: bool = False,
    requests_per_second: float | None = None,
) -> None:
    """Kjører en per-orgnr-jobb over utvalget med resume og feilhåndtering."""
    kandidater = _velg_orgnr(con, kilde, konfig.friskhet_dager, force, limit)
    totalt_i_utvalg = con.execute("SELECT count(*) FROM utvalg").fetchone()[0]
    if totalt_i_utvalg == 0:
        raise SystemExit("utvalget er tomt – kjør `bedriftdata utvalg` først")
    print(f"{kilde}: {len(kandidater)} av {totalt_i_utvalg} i utvalget skal hentes")
    if not kandidater:
        return

    rps = requests_per_second or konfig.requests_per_second
    detaljer = {"kandidater": len(kandidater), "force": force, "limit": limit, "rps": rps}
    with (
        Innlasting(con, kilde, detaljer) as logg,
        PoliteClient(requests_per_second=rps) as client,
    ):
        nye_permanente = 0
        for orgnr, naeringskode in tqdm(kandidater, unit="orgnr"):
            try:
                status, rader = jobb(con, client, orgnr)
                http_status, feilmelding = None, None
            except httpx.HTTPStatusError as feil:
                status, rader = "feilet", 0
                http_status = feil.response.status_code
                feilmelding = f"HTTP {http_status}"
            except httpx.TransportError as feil:
                status, rader = "feilet", 0
                http_status = None
                feilmelding = f"{type(feil).__name__}: {feil}"

            permanent = _oppdater_hentestatus(
                con, kilde, orgnr, status, http_status, feilmelding, naeringskode
            )
            nye_permanente += permanent
            logg.registrer(rader=rader, feil=(status == "feilet"))

        if kilde == "regnskap":
            spenn = con.execute("SELECT min(fra_dato), max(til_dato) FROM regnskap").fetchone()
        elif kilde == "roller":
            spenn = con.execute(
                "SELECT min(snapshot_dato), max(snapshot_dato) FROM rolle"
            ).fetchone()
        else:
            spenn = con.execute(
                "SELECT make_date(min(regnskapsaar), 1, 1), make_date(max(regnskapsaar), 12, 31)"
                " FROM aarsregnskap_aar"
            ).fetchone()
        logg.sett_datospenn(*spenn)
        print(
            f"  {logg.rader_skrevet:,} rader skrevet, {logg.antall_feil} feil"
            f" ({nye_permanente} markert permanent)"
        )
