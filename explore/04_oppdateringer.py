"""Utforsker oppdaterings-API-et (endringsstrøm) for Enhetsregisteret.

Dette er nøkkelen til inkrementell synkronisering: i stedet for å laste ned
hele registeret på nytt kan en database holdes oppdatert ved å polle
endringer siden forrige kjøring (via dato eller oppdateringsid).

Kjør: uv run python explore/04_oppdateringer.py
"""

import datetime as dt

import pandas as pd

from bedriftdata import brreg
from bedriftdata.http import PoliteClient
from bedriftdata.utils import sikre_datamapper


def main() -> None:
    sikre_datamapper()
    i_gaar = (dt.date.today() - dt.timedelta(days=1)).isoformat()

    rader = []
    with PoliteClient(requests_per_second=4.0) as client:
        side = 0
        while side < 5:  # 5 sider à 500 holder for å se volum og typer
            svar = client.get_json(
                brreg.OPPDATERINGER_URL,
                params={"dato": f"{i_gaar}T00:00:00.000Z", "size": 500, "page": side},
            )
            if svar is None:
                break
            elementer = svar.get("_embedded", {}).get("oppdaterteEnheter", [])
            if not elementer:
                break
            rader.extend(elementer)
            totalt = svar.get("page", {}).get("totalElements")
            side += 1

    df = pd.DataFrame(
        [
            {
                "oppdateringsid": e.get("oppdateringsid"),
                "dato": e.get("dato"),
                "orgnr": e.get("organisasjonsnummer"),
                "endringstype": e.get("endringstype"),
            }
            for e in rader
        ]
    )

    print(f"== Endringer i Enhetsregisteret siden {i_gaar} (første {len(df)} av {totalt}) ==")
    print("\n== Fordeling av endringstyper ==")
    print(df["endringstype"].value_counts().to_markdown())
    print(
        "\nPollemønster for inkrementell synk: lagre høyeste oppdateringsid og"
        " spør med ?oppdateringsid=<id+1> neste gang. Tilsvarende API finnes for"
        " underenheter og roller."
    )


if __name__ == "__main__":
    main()
