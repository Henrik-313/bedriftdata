"""Tynne wrappere rundt de åpne API-ene til Brønnøysundregistrene.

Dokumentasjon:
- Enhetsregisteret: https://data.brreg.no/enhetsregisteret/api/docs/index.html
- Regnskapsregisteret (åpne data): https://data.brreg.no/regnskapsregisteret/regnskap/
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from bedriftdata.http import PoliteClient

ENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/enheter"
UNDERENHETER_URL = "https://data.brreg.no/enhetsregisteret/api/underenheter"
ROLLER_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/{orgnr}/roller"
REGNSKAP_URL = "https://data.brreg.no/regnskapsregisteret/regnskap/{orgnr}"
OPPDATERINGER_URL = "https://data.brreg.no/enhetsregisteret/api/oppdateringer/enheter"

# Kopi av innsendte årsregnskap (PDF) – gratis og uten autentisering.
AARSREGNSKAP_AAR_URL = (
    "https://data.brreg.no/regnskapsregisteret/regnskap/aarsregnskap/kopi/{orgnr}/aar"
)
AARSREGNSKAP_PDF_URL = (
    "https://data.brreg.no/regnskapsregisteret/regnskap/aarsregnskap/kopi/{orgnr}/{aar}"
)

# Nattlige totaluttrekk (bruk disse ved masseinnlasting, ikke søke-API-et).
ENHETER_BULK_URL = "https://data.brreg.no/enhetsregisteret/api/enheter/lastned"
UNDERENHETER_BULK_URL = "https://data.brreg.no/enhetsregisteret/api/underenheter/lastned"

# Søke-API-et nekter å bla forbi de første 10 000 treffene (page * size < 10000).
MAKS_TREFF_PER_SOK = 10_000


def sok_enheter(
    client: PoliteClient,
    params: dict[str, Any],
    maks_enheter: int = 1_000,
    sidestorrelse: int = 500,
) -> Iterator[dict[str, Any]]:
    """Itererer over enheter som matcher søkeparametrene, på tvers av sider."""
    hentet = 0
    side = 0
    while hentet < maks_enheter:
        svar = client.get_json(ENHETER_URL, params={**params, "size": sidestorrelse, "page": side})
        if svar is None:
            return
        enheter = svar.get("_embedded", {}).get("enheter", [])
        if not enheter:
            return
        for enhet in enheter:
            yield enhet
            hentet += 1
            if hentet >= maks_enheter:
                return
        side += 1
        if (side + 1) * sidestorrelse > MAKS_TREFF_PER_SOK:
            return


def antall_enheter(client: PoliteClient, params: dict[str, Any]) -> int:
    """Antall treff for et søk (bruker kun metadata, henter ingen enheter)."""
    svar = client.get_json(ENHETER_URL, params={**params, "size": 1, "page": 0})
    if svar is None:
        return 0
    return int(svar.get("page", {}).get("totalElements", 0))


def hent_enhet(client: PoliteClient, orgnr: str) -> dict[str, Any] | None:
    return client.get_json(f"{ENHETER_URL}/{orgnr}")


def hent_roller(client: PoliteClient, orgnr: str) -> dict[str, Any] | None:
    return client.get_json(ROLLER_URL.format(orgnr=orgnr))


def hent_regnskap(client: PoliteClient, orgnr: str) -> list[dict[str, Any]] | None:
    """Siste innsendte årsregnskap fra det åpne regnskaps-API-et.

    Returnerer en liste med regnskap (typisk ett) eller None hvis ingenting
    er registrert for organisasjonsnummeret.
    """
    svar = client.get_json(REGNSKAP_URL.format(orgnr=orgnr))
    if svar is None:
        return None
    if isinstance(svar, dict):
        return [svar]
    return svar


def hent_aarsregnskap_aar(client: PoliteClient, orgnr: str) -> list[str] | None:
    """Hvilke år det finnes innsendt årsregnskap (PDF-kopi) for."""
    return client.get_json(AARSREGNSKAP_AAR_URL.format(orgnr=orgnr))


def hent_aarsregnskap_pdf(client: PoliteClient, orgnr: str, aar: str) -> bytes | None:
    """Laster ned innsendt årsregnskap som PDF. Returnerer None hvis det ikke finnes."""
    respons = client.get(AARSREGNSKAP_PDF_URL.format(orgnr=orgnr, aar=aar))
    if respons.status_code in (404, 410):
        return None
    respons.raise_for_status()
    return respons.content
