"""Røyktest: verifiser at endepunkter, parametre og svarstruktur stemmer.

Kjør: uv run python explore/00_roketest.py
"""

from bedriftdata import brreg
from bedriftdata.http import PoliteClient
from bedriftdata.utils import flat_nokler

EQUINOR = "923609016"

with PoliteClient() as client:
    print("== Søk på navn 'Equinor' ==")
    svar = client.get_json(brreg.ENHETER_URL, params={"navn": "Equinor", "size": 3})
    for enhet in svar.get("_embedded", {}).get("enheter", []):
        print(
            " ",
            enhet["organisasjonsnummer"],
            enhet["navn"],
            enhet.get("organisasjonsform", {}).get("kode"),
        )
    print("  totalElements:", svar.get("page", {}).get("totalElements"))

    print("\n== Filterparametre for ansatte (fraAntallAnsatte/tilAntallAnsatte) ==")
    respons = client.get(
        brreg.ENHETER_URL,
        params={"organisasjonsform": "AS", "fraAntallAnsatte": 250, "size": 1},
    )
    print("  status:", respons.status_code)
    if respons.status_code == 200:
        print(
            "  totalElements (AS >=250 ansatte):",
            respons.json().get("page", {}).get("totalElements"),
        )
    else:
        print("  feilmelding:", respons.text[:500])

    print("\n== Enkeltenhet ==")
    enhet = brreg.hent_enhet(client, EQUINOR)
    print("  toppnivånøkler:", sorted(enhet.keys()))

    print("\n== Regnskap for Equinor ==")
    regnskap = brreg.hent_regnskap(client, EQUINOR)
    if regnskap is None:
        print("  404 – ikke funnet")
    else:
        print("  antall regnskap i svar:", len(regnskap))
        forste = regnskap[0]
        print("  toppnivånøkler:", sorted(forste.keys()))
        print("  nøkkelstier (utvalg):")
        for sti in sorted(flat_nokler(forste))[:40]:
            print("   ", sti)

    print("\n== Regnskap for lite selskap (tilfeldig AS) ==")
    lite = next(
        brreg.sok_enheter(
            client,
            {"organisasjonsform": "AS", "fraAntallAnsatte": 1, "tilAntallAnsatte": 5},
            maks_enheter=1,
        )
    )
    print("  testselskap:", lite["organisasjonsnummer"], lite["navn"])
    regnskap_lite = brreg.hent_regnskap(client, lite["organisasjonsnummer"])
    print("  regnskap funnet:", regnskap_lite is not None and len(regnskap_lite) > 0)

    print("\n== Roller for Equinor ==")
    roller = brreg.hent_roller(client, EQUINOR)
    if roller:
        grupper = roller.get("rollegrupper", [])
        print("  antall rollegrupper:", len(grupper))
        print("  gruppetyper:", [g.get("type", {}).get("kode") for g in grupper])

    print("\n== Oppdateringer-API (endringsstrøm) ==")
    oppdateringer = client.get_json(
        brreg.OPPDATERINGER_URL, params={"dato": "2026-08-20T00:00:00.000Z", "size": 2}
    )
    if oppdateringer:
        elementer = oppdateringer.get("_embedded", {}).get("oppdaterteEnheter", [])
        print(
            "  fikk",
            len(elementer),
            "oppdateringer, eksempelnøkler:",
            sorted(elementer[0].keys()) if elementer else "-",
        )
