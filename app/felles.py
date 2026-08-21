"""Felles hjelpere for dashbordet: tilkobling, spørringer og formatering."""

from __future__ import annotations

import duckdb
import pandas as pd
import streamlit as st

from bedriftdata.config import last_konfig


@st.cache_resource
def _tilkobling() -> duckdb.DuckDBPyConnection:
    konfig = last_konfig()
    return duckdb.connect(str(konfig.db_sti), read_only=True)


@st.cache_data(ttl=300, show_spinner=False)
def sporr(sql: str, params: tuple = ()) -> pd.DataFrame:
    """Kjører en spørring mot basen. Nytt cursor-objekt per kall (trådsikkerhet)."""
    return _tilkobling().cursor().execute(sql, list(params)).df()


def krev_database() -> None:
    """Stopper siden med veiledning hvis databasen mangler eller er låst."""
    konfig = last_konfig()
    if not konfig.db_sti.exists():
        st.error(
            "Fant ingen database. Kjør innlastingen først:\n\n```\nuv run bedriftdata alt\n```"
        )
        st.stop()
    try:
        _tilkobling()
    except duckdb.Error as feil:
        if "lock" in str(feil).casefold():
            st.error(
                "Databasen er låst – en innlasting pågår trolig. "
                "Vent til den er ferdig og trykk «Last data på nytt» i sidemenyen."
            )
        else:
            st.error(f"Klarte ikke å åpne databasen: {feil}")
        st.stop()


def tall(verdi: float | int | None, desimaler: int = 0) -> str:
    """Norsk tallformat med hardt mellomrom som tusenskille."""
    if verdi is None or pd.isna(verdi):
        return "–"
    return f"{verdi:,.{desimaler}f}".replace(",", " ").replace(".", ",")


def prosent(andel: float | None, desimaler: int = 1) -> str:
    """Norsk prosentformat (komma som desimaltegn)."""
    if andel is None or pd.isna(andel):
        return "–"
    return f"{andel:.{desimaler}%}".replace(".", ",")


def til_oslo_tid(serie: pd.Series) -> pd.Series:
    """TIMESTAMPTZ-kolonner vises i norsk tid uten sekunder."""
    return serie.dt.tz_convert("Europe/Oslo").dt.strftime("%d.%m.%Y %H:%M")
