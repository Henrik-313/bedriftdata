"""Utforsker det åpne regnskaps-API-et: dekning, ferskhet og kvalitet på nøkkeltall.

Bruker utvalget fra 01_enhetsregisteret.py og henter siste årsregnskap for et
delutvalg. Måler:
- treffrate (hvem har regnskap tilgjengelig) per gruppe
- hvilket regnskapsår som er tilgjengelig (kun siste år via åpent API)
- feltdekning i regnskapssvarene
- konsistens: stemmer balansen (eiendeler = egenkapital + gjeld)?

Lager:
- data/samples/regnskap_utvalg.parquet
- data/samples/feltdekning_regnskap.csv
- data/raw/regnskap_eksempler.json (to komplette eksempelsvar)

Kjør: uv run python explore/02_regnskap.py
"""

from typing import Any

import httpx
import pandas as pd
from tqdm import tqdm

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

MAKS_PER_GRUPPE = 100  # ASA tas i sin helhet, andre grupper begrenses


def til_rad(orgnr: str, gruppe: str, regnskap: list[dict[str, Any]] | None) -> dict[str, Any]:
    rad: dict[str, Any] = {
        "orgnr": orgnr,
        "gruppe": gruppe,
        "funnet": regnskap is not None and len(regnskap) > 0,
        "antall_regnskap": len(regnskap) if regnskap else 0,
    }
    if not rad["funnet"]:
        return rad
    r = regnskap[0]
    sum_eiendeler = hent_nostet(r, "eiendeler.sumEiendeler")
    sum_ek_gjeld = hent_nostet(r, "egenkapitalGjeld.sumEgenkapitalGjeld")
    sum_ek = hent_nostet(r, "egenkapitalGjeld.egenkapital.sumEgenkapital")
    sum_gjeld = hent_nostet(r, "egenkapitalGjeld.gjeldOversikt.sumGjeld")
    rad.update(
        {
            "fra_dato": hent_nostet(r, "regnskapsperiode.fraDato"),
            "til_dato": hent_nostet(r, "regnskapsperiode.tilDato"),
            "valuta": r.get("valuta"),
            "oppstillingsplan": r.get("oppstillingsplan"),
            "smaa_foretak": hent_nostet(r, "regnkapsprinsipper.smaaForetak"),
            "regnskapsregler": hent_nostet(r, "regnkapsprinsipper.regnskapsregler"),
            "ikke_revidert": hent_nostet(r, "revisjon.ikkeRevidertAarsregnskap"),
            "morselskap": hent_nostet(r, "virksomhet.morselskap"),
            "sum_driftsinntekter": hent_nostet(
                r, "resultatregnskapResultat.driftsresultat.driftsinntekter.sumDriftsinntekter"
            ),
            "driftsresultat": hent_nostet(
                r, "resultatregnskapResultat.driftsresultat.driftsresultat"
            ),
            "aarsresultat": hent_nostet(r, "resultatregnskapResultat.aarsresultat"),
            "sum_eiendeler": sum_eiendeler,
            "sum_egenkapital": sum_ek,
            "sum_gjeld": sum_gjeld,
            "sum_egenkapital_gjeld": sum_ek_gjeld,
        }
    )
    if sum_eiendeler is not None and sum_ek_gjeld is not None:
        rad["balanseavvik"] = sum_eiendeler - sum_ek_gjeld
    if sum_ek_gjeld is not None and sum_ek is not None and sum_gjeld is not None:
        rad["ek_pluss_gjeld_avvik"] = sum_ek_gjeld - (sum_ek + sum_gjeld)
    return rad


def main() -> None:
    sikre_datamapper()
    utvalg = pd.read_parquet(DATA_SAMPLES / "enheter_utvalg.parquet")

    deler = []
    for gruppe, gruppedata in utvalg.groupby("gruppe"):
        n = len(gruppedata) if gruppe == "ASA" else min(MAKS_PER_GRUPPE, len(gruppedata))
        deler.append(gruppedata.head(n))
    delutvalg = pd.concat(deler, ignore_index=True)
    print(f"Henter regnskap for {len(delutvalg)} enheter ...")

    rader = []
    raa_alle: list[dict[str, Any]] = []
    eksempler: list[dict[str, Any]] = []
    with PoliteClient(requests_per_second=5.0) as client:
        for _, enhet in tqdm(list(delutvalg.iterrows()), unit="enhet"):
            # Enkelte orgnr gir vedvarende 5xx fra API-et – registreres som eget utfall.
            try:
                regnskap = brreg.hent_regnskap(client, enhet["orgnr"])
                feilkode = None
            except httpx.HTTPStatusError as exc:
                regnskap = None
                feilkode = exc.response.status_code
            rad = til_rad(enhet["orgnr"], enhet["gruppe"], regnskap)
            rad["http_feil"] = feilkode
            rader.append(rad)
            if regnskap:
                raa_alle.extend(regnskap)
                if len(eksempler) < 2:
                    eksempler.extend(regnskap)

    df = pd.DataFrame(rader)
    df.to_parquet(DATA_SAMPLES / "regnskap_utvalg.parquet", index=False)
    lagre_json(eksempler, DATA_RAW / "regnskap_eksempler.json")

    print("\n== Treffrate per gruppe ==")
    treff = (
        df.groupby("gruppe")
        .agg(
            n=("orgnr", "size"),
            treffrate=("funnet", "mean"),
            api_feil=("http_feil", lambda s: s.notna().sum()),
        )
        .reset_index()
        .sort_values("treffrate", ascending=False)
    )
    print(treff.to_markdown(index=False, floatfmt=".3f"))
    feilede = df[df["http_feil"].notna()]
    if len(feilede):
        print(f"\nOrgnr med vedvarende API-feil ({len(feilede)}):")
        print(feilede[["orgnr", "gruppe", "http_feil"]].to_markdown(index=False))

    funnet = df[df["funnet"]].copy()
    if funnet.empty:
        print("Ingen regnskap funnet – avbryter analysen.")
        return

    print("\n== Antall regnskap per svar (gir API-et historikk?) ==")
    print(df["antall_regnskap"].value_counts().sort_index().to_markdown())

    print("\n== Regnskapsår (år i tilDato) ==")
    funnet["regnskapsaar"] = pd.to_datetime(funnet["til_dato"]).dt.year
    print(funnet["regnskapsaar"].value_counts().sort_index().to_markdown())

    print("\n== Oppstillingsplan og prinsipper ==")
    print(funnet["oppstillingsplan"].value_counts(dropna=False).to_markdown())
    print()
    print(funnet["regnskapsregler"].value_counts(dropna=False).to_markdown())

    print("\n== Dekning av nøkkeltall blant treff ==")
    nokkeltall = [
        "sum_driftsinntekter",
        "driftsresultat",
        "aarsresultat",
        "sum_eiendeler",
        "sum_egenkapital",
        "sum_gjeld",
    ]
    dekning = pd.DataFrame(
        [{"felt": felt, "andel_utfylt": funnet[felt].notna().mean()} for felt in nokkeltall]
    )
    print(dekning.to_markdown(index=False, floatfmt=".3f"))

    print("\n== Balansekontroll (eiendeler - (egenkapital+gjeld)) ==")
    med_balanse = funnet.dropna(subset=["balanseavvik"])
    avvik = (med_balanse["balanseavvik"].abs() > 1).mean() if len(med_balanse) else float("nan")
    print(f"  enheter med balansetall: {len(med_balanse)} av {len(funnet)}")
    print(f"  andel med avvik > 1 kr: {avvik:.4f}")
    if len(med_balanse):
        print(f"  størst absolutt avvik: {med_balanse['balanseavvik'].abs().max():,.0f} kr")

    print("\n== Valuta ==")
    print(funnet["valuta"].value_counts(dropna=False).to_markdown())

    print("\n== Feltdekning i rå regnskapssvar ==")
    dekning_raa = feltdekning(raa_alle)
    dekning_df = (
        pd.DataFrame([{"felt": f, "andel": a / len(raa_alle)} for f, a in dekning_raa.items()])
        .sort_values("andel", ascending=False)
        .reset_index(drop=True)
    )
    dekning_df.to_csv(DATA_SAMPLES / "feltdekning_regnskap.csv", index=False)
    print(f"  {len(dekning_df)} ulike feltstier observert, lagret til feltdekning_regnskap.csv")
    print(dekning_df.head(25).to_markdown(index=False, floatfmt=".3f"))


if __name__ == "__main__":
    main()
