"""Utforsker Enhetsregisteret: bestand, feltdekning og uttrekk av stratifisert utvalg.

Lager:
- data/samples/enheter_utvalg.parquet   (flatt utvalg til bruk i senere skript)
- data/raw/enheter_utvalg_raa.json      (rå API-svar for feltanalyse)
- data/samples/feltdekning_enheter.csv  (andel av utvalget som har hvert felt)

Kjør: uv run python explore/01_enhetsregisteret.py
"""

from typing import Any

import pandas as pd

from bedriftdata import brreg
from bedriftdata.http import PoliteClient
from bedriftdata.utils import (
    DATA_RAW,
    DATA_SAMPLES,
    feltdekning,
    hent_nostet,
    lagre_json,
    sikre_datamapper,
)

ORGFORMER = ["AS", "ASA", "ENK", "ANS", "DA", "NUF", "SA", "STI", "FLI", "KS", "SAM", "KOMM"]

ANSATTBUCKETS = [
    ("0", {"fraAntallAnsatte": 0, "tilAntallAnsatte": 0}),
    ("1-9", {"fraAntallAnsatte": 1, "tilAntallAnsatte": 9}),
    ("10-49", {"fraAntallAnsatte": 10, "tilAntallAnsatte": 49}),
    ("50-249", {"fraAntallAnsatte": 50, "tilAntallAnsatte": 249}),
    ("250+", {"fraAntallAnsatte": 250}),
]

UTVALG_PER_GRUPPE = 150


def til_rad(enhet: dict[str, Any], gruppe: str) -> dict[str, Any]:
    return {
        "gruppe": gruppe,
        "orgnr": enhet["organisasjonsnummer"],
        "navn": enhet.get("navn"),
        "orgform": hent_nostet(enhet, "organisasjonsform.kode"),
        "naeringskode": hent_nostet(enhet, "naeringskode1.kode"),
        "naering_beskrivelse": hent_nostet(enhet, "naeringskode1.beskrivelse"),
        "sektorkode": hent_nostet(enhet, "institusjonellSektorkode.kode"),
        "antall_ansatte": enhet.get("antallAnsatte"),
        "har_registrert_ansatte": enhet.get("harRegistrertAntallAnsatte"),
        "kommunenummer": hent_nostet(enhet, "forretningsadresse.kommunenummer"),
        "kommune": hent_nostet(enhet, "forretningsadresse.kommune"),
        "stiftelsesdato": enhet.get("stiftelsesdato"),
        "registreringsdato": enhet.get("registreringsdatoEnhetsregisteret"),
        "siste_aarsregnskap": enhet.get("sisteInnsendteAarsregnskap"),
        "konkurs": enhet.get("konkurs"),
        "under_avvikling": enhet.get("underAvvikling"),
        "i_mvaregisteret": enhet.get("registrertIMvaregisteret"),
        "i_foretaksregisteret": enhet.get("registrertIForetaksregisteret"),
        "er_i_konsern": enhet.get("erIKonsern"),
        "har_hjemmeside": bool(enhet.get("hjemmeside")),
    }


def main() -> None:
    sikre_datamapper()
    rader: list[dict[str, Any]] = []
    raa: list[dict[str, Any]] = []

    with PoliteClient(requests_per_second=4.0) as client:
        print("== Bestand per organisasjonsform ==")
        bestand = []
        for form in ORGFORMER:
            antall = brreg.antall_enheter(client, {"organisasjonsform": form})
            bestand.append({"orgform": form, "antall_registrert": antall})
        bestand_df = pd.DataFrame(bestand).sort_values("antall_registrert", ascending=False)
        print(bestand_df.to_markdown(index=False))
        bestand_df.to_csv(DATA_SAMPLES / "bestand_orgformer.csv", index=False)

        print("\n== Bestand AS per ansattgruppe ==")
        for navn, filter_ in ANSATTBUCKETS:
            antall = brreg.antall_enheter(client, {"organisasjonsform": "AS", **filter_})
            print(f"  AS {navn:>7}: {antall:>8,}")

        print("\n== Henter utvalg ==")
        for navn, filter_ in ANSATTBUCKETS:
            gruppe = f"AS {navn}"
            for enhet in brreg.sok_enheter(
                client, {"organisasjonsform": "AS", **filter_}, maks_enheter=UTVALG_PER_GRUPPE
            ):
                raa.append(enhet)
                rader.append(til_rad(enhet, gruppe))
            print(f"  {gruppe}: {sum(r['gruppe'] == gruppe for r in rader)} enheter")

        for enhet in brreg.sok_enheter(client, {"organisasjonsform": "ASA"}, maks_enheter=500):
            raa.append(enhet)
            rader.append(til_rad(enhet, "ASA"))
        print(f"  ASA: {sum(r['gruppe'] == 'ASA' for r in rader)} enheter (alle)")

        for form in ["ENK", "NUF", "SA"]:
            for enhet in brreg.sok_enheter(
                client, {"organisasjonsform": form}, maks_enheter=UTVALG_PER_GRUPPE
            ):
                raa.append(enhet)
                rader.append(til_rad(enhet, form))
            print(f"  {form}: {sum(r['gruppe'] == form for r in rader)} enheter")

    df = pd.DataFrame(rader)
    df.to_parquet(DATA_SAMPLES / "enheter_utvalg.parquet", index=False)
    lagre_json(raa, DATA_RAW / "enheter_utvalg_raa.json")

    print(f"\n== Utvalg lagret: {len(df)} enheter ==")

    print("\n== Feltdekning i utvalget (andel enheter med feltet) ==")
    dekning = feltdekning(raa)
    dekning_df = (
        pd.DataFrame(
            [{"felt": felt, "andel": antall / len(raa)} for felt, antall in dekning.items()]
        )
        .sort_values("andel", ascending=False)
        .reset_index(drop=True)
    )
    dekning_df.to_csv(DATA_SAMPLES / "feltdekning_enheter.csv", index=False)
    hovedfelter = [
        "organisasjonsnummer",
        "navn",
        "organisasjonsform.kode",
        "naeringskode1.kode",
        "antallAnsatte",
        "forretningsadresse.kommunenummer",
        "stiftelsesdato",
        "sisteInnsendteAarsregnskap",
        "hjemmeside",
        "institusjonellSektorkode.kode",
        "registreringsdatoEnhetsregisteret",
        "erIKonsern",
    ]
    utvalg_dekning = dekning_df[dekning_df["felt"].isin(hovedfelter)]
    print(utvalg_dekning.to_markdown(index=False, floatfmt=".3f"))

    print("\n== Nøkkeltall per gruppe ==")
    oppsummering = (
        df.groupby("gruppe")
        .agg(
            n=("orgnr", "size"),
            med_naeringskode=("naeringskode", lambda s: s.notna().mean()),
            med_ansattetall=("har_registrert_ansatte", "mean"),
            med_regnskap=("siste_aarsregnskap", lambda s: s.notna().mean()),
            konkurs=("konkurs", "mean"),
        )
        .reset_index()
    )
    print(oppsummering.to_markdown(index=False, floatfmt=".3f"))


if __name__ == "__main__":
    main()
