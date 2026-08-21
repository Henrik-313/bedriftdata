"""Kjøringslogg: alle ingest-jobber rapporterer til innlasting-tabellen."""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

import duckdb


class Innlasting:
    """Kontekstmanager som logger en ingest-kjøring i innlasting-tabellen.

    Skriver en 'kjorer'-rad ved start og oppdaterer status/tellinger ved slutt –
    også ved feil ('feilet') og Ctrl+C ('avbrutt'). Unntak slippes videre.
    """

    def __init__(
        self,
        con: duckdb.DuckDBPyConnection,
        kilde: str,
        detaljer: dict[str, Any] | None = None,
    ) -> None:
        self._con = con
        self._kilde = kilde
        self._detaljer = detaljer or {}
        self.rader_skrevet = 0
        self.antall_feil = 0
        self.min_dato: dt.date | None = None
        self.max_dato: dt.date | None = None
        self._id: int | None = None

    def __enter__(self) -> Innlasting:
        rad = self._con.execute(
            "INSERT INTO innlasting (kilde, startet_tid, status, detaljer)"
            " VALUES (?, ?, 'kjorer', ?) RETURNING innlasting_id",
            [self._kilde, dt.datetime.now(dt.UTC), json.dumps(self._detaljer, ensure_ascii=False)],
        ).fetchone()
        self._id = rad[0]
        return self

    def registrer(self, rader: int = 0, feil: int = 0) -> None:
        self.rader_skrevet += rader
        self.antall_feil += feil

    def sett_datospenn(self, min_dato: dt.date | None, max_dato: dt.date | None) -> None:
        self.min_dato = min_dato
        self.max_dato = max_dato

    def __exit__(self, exc_type: type | None, exc: BaseException | None, _tb: object) -> None:
        if exc_type is None:
            status = "ok"
        elif issubclass(exc_type, KeyboardInterrupt):
            status = "avbrutt"
        else:
            status = "feilet"
            self._detaljer["feil"] = f"{exc_type.__name__}: {exc}"
        self._con.execute(
            "UPDATE innlasting SET ferdig_tid = ?, status = ?, rader_skrevet = ?,"
            " antall_feil = ?, min_dato = ?, max_dato = ?, detaljer = ?"
            " WHERE innlasting_id = ?",
            [
                dt.datetime.now(dt.UTC),
                status,
                self.rader_skrevet,
                self.antall_feil,
                self.min_dato,
                self.max_dato,
                json.dumps(self._detaljer, ensure_ascii=False),
                self._id,
            ],
        )
