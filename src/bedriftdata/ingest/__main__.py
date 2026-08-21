"""CLI for innlastingsjobbene: `uv run bedriftdata <kommando>`."""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

from bedriftdata import db
from bedriftdata.config import Konfig, last_konfig

LAAST_MELDING = (
    "Databasen er låst av en annen prosess – kjører dashbordet?\n"
    "Stopp det (Ctrl+C i streamlit-terminalen) og prøv igjen."
)


def _status(con: duckdb.DuckDBPyConnection, _konfig: Konfig, _args: argparse.Namespace) -> None:
    oversikt = con.execute(
        "SELECT kilde, rader, dato_fra, dato_til, siste_status, siste_ferdig,"
        " siste_rader, siste_feil FROM v_kildeoversikt ORDER BY kilde"
    ).df()
    print("== Kildeoversikt ==")
    print(oversikt.to_markdown(index=False))

    hentestatus = con.execute(
        "SELECT kilde, status, permanent_feil, count(*) AS antall"
        " FROM hentestatus GROUP BY ALL ORDER BY kilde, status"
    ).df()
    if len(hentestatus):
        print("\n== Hentestatus per orgnr-kilde ==")
        print(hentestatus.to_markdown(index=False))

    kjoringer = con.execute(
        "SELECT kilde, startet_tid, status, rader_skrevet, antall_feil"
        " FROM innlasting ORDER BY startet_tid DESC LIMIT 10"
    ).df()
    if len(kjoringer):
        print("\n== Siste kjøringer ==")
        print(kjoringer.to_markdown(index=False))


def _enheter(con: duckdb.DuckDBPyConnection, konfig: Konfig, args: argparse.Namespace) -> None:
    from bedriftdata.ingest import enheter

    enheter.kjor(con, konfig, hopp_over_nedlasting=getattr(args, "gjenbruk_fil", False))


def _utvalg(con: duckdb.DuckDBPyConnection, konfig: Konfig, _args: argparse.Namespace) -> None:
    from bedriftdata.ingest import utvalg

    utvalg.kjor(con, konfig)


def _regnskap(con: duckdb.DuckDBPyConnection, konfig: Konfig, args: argparse.Namespace) -> None:
    from bedriftdata.ingest import regnskap

    regnskap.kjor(
        con, konfig, limit=getattr(args, "limit", None), force=getattr(args, "force", False)
    )


def _roller(con: duckdb.DuckDBPyConnection, konfig: Konfig, args: argparse.Namespace) -> None:
    from bedriftdata.ingest import roller

    roller.kjor(
        con, konfig, limit=getattr(args, "limit", None), force=getattr(args, "force", False)
    )


def _aarsregnskap(con: duckdb.DuckDBPyConnection, konfig: Konfig, args: argparse.Namespace) -> None:
    from bedriftdata.ingest import aarsregnskap

    aarsregnskap.kjor(
        con, konfig, limit=getattr(args, "limit", None), force=getattr(args, "force", False)
    )


def _valutakurser(
    con: duckdb.DuckDBPyConnection, konfig: Konfig, _args: argparse.Namespace
) -> None:
    from bedriftdata.ingest import valutakurser

    valutakurser.kjor(con, konfig)


def _alt(con: duckdb.DuckDBPyConnection, konfig: Konfig, args: argparse.Namespace) -> None:
    _enheter(con, konfig, args)
    _utvalg(con, konfig, args)
    _regnskap(con, konfig, args)
    _roller(con, konfig, args)
    _aarsregnskap(con, konfig, args)
    _valutakurser(con, konfig, args)
    _status(con, konfig, args)


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="bedriftdata",
        description="Laster åpne norske bedriftsdata inn i en lokal DuckDB-base.",
    )
    parser.add_argument("--db", help="databasesti (overstyrer config)")
    parser.add_argument("--config", help="sti til config.toml")
    sub = parser.add_subparsers(dest="kommando", required=True)

    sub.add_parser("init", help="opprett/oppgrader databaseskjemaet")
    p_enheter = sub.add_parser("enheter", help="last hele Enhetsregisteret (nattlig bulk-fil)")
    p_enheter.add_argument(
        "--gjenbruk-fil",
        action="store_true",
        help="bruk allerede nedlastet bulk-fil hvis den finnes",
    )
    sub.add_parser("utvalg", help="bygg høsteutvalget fra config.toml")
    for navn, hjelp in [
        ("regnskap", "hent siste årsregnskap (JSON) for utvalget"),
        ("roller", "hent roller for utvalget (snapshot per dato)"),
        ("aarsregnskap", "hent tilgjengelige PDF-årganger for utvalget"),
    ]:
        p_jobb = sub.add_parser(navn, help=hjelp)
        p_jobb.add_argument("--limit", type=int, help="maks antall orgnr denne kjøringen")
        p_jobb.add_argument(
            "--force", action="store_true", help="ignorer friskhetsvindu og permanente feil"
        )
    sub.add_parser("valutakurser", help="hent valutakurser fra Norges Bank")
    sub.add_parser("status", help="vis kildeoversikt, hentestatus og siste kjøringer")
    p_alt = sub.add_parser("alt", help="kjør alle jobber i riktig rekkefølge")
    p_alt.add_argument("--gjenbruk-fil", action="store_true", help=argparse.SUPPRESS)

    args = parser.parse_args()
    konfig = last_konfig(Path(args.config) if args.config else None)
    db_sti = Path(args.db) if args.db else konfig.db_sti

    try:
        con = db.koble_til(db_sti)
    except duckdb.Error as feil:
        if "lock" in str(feil).casefold():
            raise SystemExit(LAAST_MELDING) from feil
        raise
    try:
        db.init_skjema(con)
        kommandoer = {
            "init": lambda *_: print(f"Skjema klart i {db_sti}"),
            "enheter": _enheter,
            "utvalg": _utvalg,
            "regnskap": _regnskap,
            "roller": _roller,
            "aarsregnskap": _aarsregnskap,
            "valutakurser": _valutakurser,
            "status": _status,
            "alt": _alt,
        }
        kommandoer[args.kommando](con, konfig, args)
    finally:
        con.close()


if __name__ == "__main__":
    main()
