"""Tester for lagringslaget: skjema-idempotens, insert-semantikk og views."""

import datetime as dt

import duckdb
import pytest

from bedriftdata.db import init_skjema, sett_inn
from bedriftdata.transform import regnskap_til_rad, roller_til_rader
from tests.test_transform import HENTET, ROLLER_SVAR, lag_regnskap


@pytest.fixture
def con():
    con = duckdb.connect(":memory:")
    init_skjema(con)
    yield con
    con.close()


def test_init_skjema_er_idempotent(con):
    init_skjema(con)  # andre gang skal ikke feile eller duplisere seed
    assert con.execute("SELECT count(*) FROM kilde").fetchone()[0] == 6
    assert con.execute("SELECT count(*) FROM fylke").fetchone()[0] == 17


def test_views_kjorbare_paa_tom_base(con):
    oversikt = con.execute("SELECT * FROM v_kildeoversikt").df()
    assert len(oversikt) == 6
    assert oversikt["rader"].fillna(0).sum() == 0
    con.execute("SELECT * FROM v_enhet_fylke").df()
    con.execute("SELECT * FROM v_regnskap_kvalitet").df()


def test_regnskapsrad_passer_skjemaet_og_erstattes(con):
    rad = regnskap_til_rad("999999999", lag_regnskap(1_000_000, 400_000, 600_000), HENTET)

    sett_inn(con, "regnskap", [rad])
    sett_inn(con, "regnskap", [rad])  # samme PK -> erstatter, ikke duplikat

    antall, aar = con.execute("SELECT count(*), max(regnskapsaar) FROM regnskap").fetchone()
    assert antall == 1
    assert aar == 2025

    til_dato = con.execute("SELECT til_dato FROM regnskap").fetchone()[0]
    assert til_dato == dt.date(2025, 12, 31)  # streng castes til DATE


def test_regnskap_akkumulerer_historikk(con):
    rad_2025 = regnskap_til_rad("999999999", lag_regnskap(1_000_000, 400_000, 600_000), HENTET)
    rad_2024 = dict(rad_2025, regnskapsaar=2024, fra_dato="2024-01-01", til_dato="2024-12-31")

    sett_inn(con, "regnskap", [rad_2025, rad_2024])

    assert con.execute("SELECT count(*) FROM regnskap").fetchone()[0] == 2


def test_rolle_snapshot_delete_insert_er_idempotent(con):
    rader = roller_til_rader("999999999", ROLLER_SVAR, dt.date(2026, 8, 21), HENTET)

    for _ in range(2):  # samme snapshot lastes to ganger
        con.execute(
            "DELETE FROM rolle WHERE orgnr = ? AND snapshot_dato = ?",
            ["999999999", dt.date(2026, 8, 21)],
        )
        sett_inn(con, "rolle", rader, erstatt=False)

    assert con.execute("SELECT count(*) FROM rolle").fetchone()[0] == 3
    foedselsdato = con.execute(
        "SELECT person_foedselsdato FROM rolle WHERE rolletype = 'LEDE'"
    ).fetchone()[0]
    assert foedselsdato == dt.date(1980, 1, 15)


def test_kildeoversikt_viser_siste_innlasting(con):
    for status, startet in [("ok", "2026-08-20 10:00:00+00"), ("feilet", "2026-08-21 10:00:00+00")]:
        con.execute(
            "INSERT INTO innlasting (kilde, startet_tid, status, rader_skrevet)"
            " VALUES ('regnskap', ?, ?, 42)",
            [startet, status],
        )
    rad = con.execute(
        "SELECT siste_status FROM v_kildeoversikt WHERE kilde = 'regnskap'"
    ).fetchone()
    assert rad[0] == "feilet"  # nyeste kjøring vinner
