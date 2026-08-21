"""Utforsker roller-API-et: styre, daglig leder, revisor m.m.

Måler treffrate og innhold (rolletyper, person vs. juridisk enhet,
fødselsdato-dekning) for et delutvalg fra 01_enhetsregisteret.py.

Lager: data/samples/roller_utvalg.parquet

Kjør: uv run python explore/03_roller.py
"""

from typing import Any

import pandas as pd
from tqdm import tqdm

from bedriftdata import brreg
from bedriftdata.http import PoliteClient
from bedriftdata.utils import DATA_RAW, DATA_SAMPLES, lagre_json, sikre_datamapper

MAKS_PER_GRUPPE = 40


def main() -> None:
    sikre_datamapper()
    utvalg = pd.read_parquet(DATA_SAMPLES / "enheter_utvalg.parquet")
    delutvalg = utvalg.groupby("gruppe").head(MAKS_PER_GRUPPE).reset_index(drop=True)
    print(f"Henter roller for {len(delutvalg)} enheter ...")

    rader: list[dict[str, Any]] = []
    eksempel: dict[str, Any] | None = None
    with PoliteClient(requests_per_second=5.0) as client:
        for _, enhet in tqdm(list(delutvalg.iterrows()), unit="enhet"):
            svar = brreg.hent_roller(client, enhet["orgnr"])
            grupper = (svar or {}).get("rollegrupper", [])
            roller = [rolle for gruppe in grupper for rolle in gruppe.get("roller", [])]
            personer = [r for r in roller if "person" in r]
            enheter_som_rolle = [r for r in roller if "enhet" in r]
            rader.append(
                {
                    "orgnr": enhet["orgnr"],
                    "gruppe": enhet["gruppe"],
                    "funnet": bool(grupper),
                    "antall_rollegrupper": len(grupper),
                    "gruppetyper": ",".join(
                        sorted(g.get("type", {}).get("kode", "?") for g in grupper)
                    ),
                    "antall_roller": len(roller),
                    "antall_personroller": len(personer),
                    "antall_enhetsroller": len(enheter_som_rolle),
                    "personer_med_foedselsdato": sum(
                        1 for r in personer if r.get("person", {}).get("fodselsdato")
                    ),
                }
            )
            if eksempel is None and grupper:
                eksempel = svar

    if eksempel:
        lagre_json(eksempel, DATA_RAW / "roller_eksempel.json")

    df = pd.DataFrame(rader)
    df.to_parquet(DATA_SAMPLES / "roller_utvalg.parquet", index=False)

    print("\n== Treffrate per gruppe ==")
    print(
        df.groupby("gruppe")
        .agg(
            n=("orgnr", "size"),
            treffrate=("funnet", "mean"),
            roller_snitt=("antall_roller", "mean"),
        )
        .reset_index()
        .to_markdown(index=False, floatfmt=".3f")
    )

    print("\n== Vanligste kombinasjoner av rollegrupper ==")
    print(df[df["funnet"]]["gruppetyper"].value_counts().head(12).to_markdown())

    personroller = df[df["antall_personroller"] > 0]
    if len(personroller):
        andel = (
            personroller["personer_med_foedselsdato"].sum()
            / personroller["antall_personroller"].sum()
        )
        print(f"\nAndel personroller med fødselsdato: {andel:.3f}")
        print("(Personer identifiseres med navn + fødselsdato – ikke fødselsnummer.)")


if __name__ == "__main__":
    main()
