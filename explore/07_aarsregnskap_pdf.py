"""Utforsker gratis PDF-kopier av innsendte årsregnskap (med noter/årsberetning).

Det åpne JSON-API-et gir bare siste år, men PDF-kopiene har historikk.
Her måles: hvor mange år som finnes per gruppe, og at nedlasting fungerer.

Lager:
- data/samples/aarsregnskap_tilgjengelighet.parquet
- data/raw/aarsregnskap_eksempel_*.pdf (to eksempler)

Kjør: uv run python explore/07_aarsregnskap_pdf.py
"""

import httpx
import pandas as pd
from tqdm import tqdm

from bedriftdata import brreg
from bedriftdata.http import PoliteClient
from bedriftdata.utils import DATA_RAW, DATA_SAMPLES, sikre_datamapper

MAKS_PER_GRUPPE = 15  # PDF-metadata-oppslag er billige, men vi holder oss beskjedne
EKSEMPLER = [("923609016", "2015"), ("923609016", "2024")]  # Equinor, gammelt og nytt år


def main() -> None:
    sikre_datamapper()
    utvalg = pd.read_parquet(DATA_SAMPLES / "enheter_utvalg.parquet")
    delutvalg = utvalg.groupby("gruppe").head(MAKS_PER_GRUPPE).reset_index(drop=True)
    print(f"Sjekker tilgjengelige årganger for {len(delutvalg)} enheter ...")

    rader = []
    with PoliteClient(requests_per_second=4.0) as client:
        for _, enhet in tqdm(list(delutvalg.iterrows()), unit="enhet"):
            try:
                aar = brreg.hent_aarsregnskap_aar(client, enhet["orgnr"]) or []
            except httpx.HTTPStatusError:
                aar = []
            rader.append(
                {
                    "orgnr": enhet["orgnr"],
                    "gruppe": enhet["gruppe"],
                    "antall_aar": len(aar),
                    "foerste_aar": min(aar) if aar else None,
                    "siste_aar": max(aar) if aar else None,
                }
            )

        print("\nLaster ned eksempel-PDF-er ...")
        for orgnr, aar in EKSEMPLER:
            pdf = brreg.hent_aarsregnskap_pdf(client, orgnr, aar)
            if pdf is None:
                print(f"  {orgnr}/{aar}: ikke funnet")
                continue
            sti = DATA_RAW / f"aarsregnskap_eksempel_{orgnr}_{aar}.pdf"
            sti.write_bytes(pdf)
            print(f"  {orgnr}/{aar}: {len(pdf) / 1024:,.0f} kB -> {sti.name}")

    df = pd.DataFrame(rader)
    df.to_parquet(DATA_SAMPLES / "aarsregnskap_tilgjengelighet.parquet", index=False)

    print("\n== Tilgjengelige PDF-årganger per gruppe ==")
    print(
        df.groupby("gruppe")
        .agg(
            n=("orgnr", "size"),
            har_pdf=("antall_aar", lambda s: (s > 0).mean()),
            aar_snitt=("antall_aar", "mean"),
            aar_maks=("antall_aar", "max"),
            eldste=("foerste_aar", "min"),
        )
        .reset_index()
        .to_markdown(index=False, floatfmt=".2f")
    )


if __name__ == "__main__":
    main()
