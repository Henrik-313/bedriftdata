"""Valutakurser fra Norges Banks åpne API (SDMX).

API-et krever en reell User-Agent (403 ellers) – PoliteClient setter det.
Kurser normaliseres til NOK per 1 enhet valuta ved å dele på 10^UNIT_MULT
(enkelte valutaer kvoteres per 100).
"""

from __future__ import annotations

from io import StringIO

import pandas as pd

from bedriftdata.http import PoliteClient

VALUTAKURS_URL = "https://data.norges-bank.no/api/data/EXR/B.{valutaer}.NOK.SP"


def hent_valutakurser(client: PoliteClient, valutaer: list[str], start_aar: int) -> pd.DataFrame:
    """Daglige midtkurser. Returnerer kolonnene valuta, dato, kurs_nok."""
    respons = client.get(
        VALUTAKURS_URL.format(valutaer="+".join(valutaer)),
        params={"format": "csv", "startPeriod": str(start_aar), "locale": "en"},
        headers={"Accept": "text/csv"},
    )
    respons.raise_for_status()

    df = pd.read_csv(StringIO(respons.text))
    if len(df.columns) == 1:  # enkelte SDMX-CSV-varianter bruker semikolon
        df = pd.read_csv(StringIO(respons.text), sep=";")
    df.columns = [str(kolonne).upper() for kolonne in df.columns]

    df["kurs_nok"] = df["OBS_VALUE"] / (10.0 ** df["UNIT_MULT"].fillna(0))
    resultat = df.rename(columns={"BASE_CUR": "valuta", "TIME_PERIOD": "dato"})
    return resultat[["valuta", "dato", "kurs_nok"]]
