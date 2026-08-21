"""Utforsker aksjekursdata for Oslo Børs-noterte selskaper via yfinance.

To spørsmål:
1. Hvor god er kvaliteten på kursdata for .OL-tickere (hull, historikk, felter)?
2. Hvor godt lar tickere seg koble til organisasjonsnummer via navnesøk i
   Enhetsregisteret? (Viktig for å koble kurs mot regnskap/registerdata.)

Lager:
- data/samples/kurser_utvalg.parquet
- data/samples/ticker_orgnr_kobling.csv

Kjør: uv run python explore/05_aksjekurs.py
"""

import pandas as pd
import yfinance as yf

from bedriftdata import brreg
from bedriftdata.http import PoliteClient
from bedriftdata.utils import DATA_SAMPLES, sikre_datamapper

# Et lite, variert utvalg: store OBX-selskaper + noen utenlandskregistrerte
# (Subsea 7, Frontline) som tester grensene for orgnr-kobling.
TICKERE = {
    "EQNR.OL": "Equinor ASA",
    "DNB.OL": "DNB Bank ASA",
    "TEL.OL": "Telenor ASA",
    "NHY.OL": "Norsk Hydro ASA",
    "ORK.OL": "Orkla ASA",
    "YAR.OL": "Yara International ASA",
    "MOWI.OL": "Mowi ASA",
    "AKRBP.OL": "Aker BP ASA",
    "SALM.OL": "SalMar ASA",
    "KOG.OL": "Kongsberg Gruppen ASA",
    "STB.OL": "Storebrand ASA",
    "TOM.OL": "Tomra Systems ASA",
    "NOD.OL": "Nordic Semiconductor ASA",
    "SUBC.OL": "Subsea 7 S.A.",
    "FRO.OL": "Frontline plc",
}


def hent_kurser() -> pd.DataFrame:
    data = yf.download(
        tickers=list(TICKERE),
        period="2y",
        interval="1d",
        group_by="ticker",
        auto_adjust=True,
        progress=False,
        threads=False,
    )
    rader = []
    for ticker in TICKERE:
        if ticker not in data.columns.get_level_values(0):
            rader.append({"ticker": ticker, "antall_dager": 0})
            continue
        serie = data[ticker].dropna(how="all")
        handelsdager = pd.bdate_range(serie.index.min(), serie.index.max())
        rader.append(
            {
                "ticker": ticker,
                "antall_dager": len(serie),
                "foerste_dato": serie.index.min().date().isoformat(),
                "siste_dato": serie.index.max().date().isoformat(),
                "manglende_virkedager": len(handelsdager) - len(serie),
                "andel_close_utfylt": serie["Close"].notna().mean(),
                "andel_volum_utfylt": serie["Volume"].notna().mean(),
            }
        )
    langt = (
        data.stack(level=0, future_stack=True)
        .rename_axis(["dato", "ticker"])
        .reset_index()
        .dropna(subset=["Close"])
    )
    langt.to_parquet(DATA_SAMPLES / "kurser_utvalg.parquet", index=False)
    return pd.DataFrame(rader)


def koble_mot_orgnr() -> pd.DataFrame:
    """Prøver å finne orgnr for hvert selskap via navnesøk i Enhetsregisteret."""
    rader = []
    with PoliteClient(requests_per_second=4.0) as client:
        for ticker, navn in TICKERE.items():
            sokenavn = navn.removesuffix(" ASA").removesuffix(" S.A.").removesuffix(" plc")
            treff = list(brreg.sok_enheter(client, {"navn": sokenavn}, maks_enheter=5))
            eksakte = [t for t in treff if t.get("navn", "").casefold() == navn.casefold()]
            beste = eksakte[0] if eksakte else (treff[0] if treff else None)
            rader.append(
                {
                    "ticker": ticker,
                    "selskapsnavn": navn,
                    "antall_treff": len(treff),
                    "eksakt_navnetreff": bool(eksakte),
                    "orgnr": beste["organisasjonsnummer"] if beste else None,
                    "registernavn": beste["navn"] if beste else None,
                    "orgform": (beste.get("organisasjonsform", {}) or {}).get("kode")
                    if beste
                    else None,
                }
            )
    df = pd.DataFrame(rader)
    df.to_csv(DATA_SAMPLES / "ticker_orgnr_kobling.csv", index=False)
    return df


def main() -> None:
    sikre_datamapper()

    print("== Kursdata (yfinance, 2 år, daglig) ==")
    kvalitet = hent_kurser()
    print(kvalitet.to_markdown(index=False, floatfmt=".3f"))

    print("\n== Kobling ticker -> orgnr via navnesøk i Enhetsregisteret ==")
    kobling = koble_mot_orgnr()
    print(kobling.to_markdown(index=False))
    print(
        "\nMerk: eksakt navnetreff er nødvendig, men ikke tilstrekkelig – kobling bør"
        " kvalitetssikres manuelt eller via ISIN/LEI. Utenlandskregistrerte utstedere"
        " (f.eks. Subsea 7, Frontline) har ikke norsk orgnr med samme navneform."
    )


if __name__ == "__main__":
    main()
