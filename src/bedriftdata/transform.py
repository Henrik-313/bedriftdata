"""Rene transformasjoner fra API-JSON til databaserader.

Ingen I/O her – funksjonene tar dicts og returnerer dicts som matcher
tabellene i db.py. Enhet-mappingen skjer i SQL (ingest/enheter.py) siden
bulk-filen leses direkte av DuckDB.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import Any

from bedriftdata.utils import hent_nostet

# Terskel for kvalitetsflagget: |eiendeler - (EK + gjeld)| relativt til eiendeler.
# Avvik under dette er avrunding til hele tusen i innsendte tall.
BALANSEAVVIK_TERSKEL = 0.001


def regnskap_til_rad(
    orgnr: str, regnskap: dict[str, Any], hentet_tid: dt.datetime
) -> dict[str, Any]:
    """Flater ett regnskapsobjekt fra det åpne regnskaps-API-et til en regnskap-rad.

    NB: nøklene `regnkapsprinsipper` og `sumInnskuttEgenkaptial` er API-ets egne
    skrivefeil og må brukes ordrett.
    """
    til_dato = hent_nostet(regnskap, "regnskapsperiode.tilDato")
    sum_eiendeler = hent_nostet(regnskap, "eiendeler.sumEiendeler")
    sum_ek = hent_nostet(regnskap, "egenkapitalGjeld.egenkapital.sumEgenkapital")
    sum_gjeld = hent_nostet(regnskap, "egenkapitalGjeld.gjeldOversikt.sumGjeld")

    balanseavvik = None
    flagg = False
    if sum_eiendeler is not None and sum_ek is not None and sum_gjeld is not None:
        balanseavvik = sum_eiendeler - (sum_ek + sum_gjeld)
        flagg = abs(balanseavvik) / max(abs(sum_eiendeler), 1.0) > BALANSEAVVIK_TERSKEL

    return {
        "orgnr": orgnr,
        "regnskapsaar": int(til_dato[:4]) if til_dato else None,
        "regnskapstype": regnskap.get("regnskapstype") or "SELSKAP",
        "regnskap_id": regnskap.get("id"),
        "journalnr": regnskap.get("journalnr"),
        "fra_dato": hent_nostet(regnskap, "regnskapsperiode.fraDato"),
        "til_dato": til_dato,
        "valuta": regnskap.get("valuta"),
        "oppstillingsplan": regnskap.get("oppstillingsplan"),
        "avviklingsregnskap": regnskap.get("avviklingsregnskap"),
        "smaa_foretak": hent_nostet(regnskap, "regnkapsprinsipper.smaaForetak"),
        "regnskapsregler": hent_nostet(regnskap, "regnkapsprinsipper.regnskapsregler"),
        "ikke_revidert": hent_nostet(regnskap, "revisjon.ikkeRevidertAarsregnskap"),
        "morselskap": hent_nostet(regnskap, "virksomhet.morselskap"),
        "sum_driftsinntekter": hent_nostet(
            regnskap, "resultatregnskapResultat.driftsresultat.driftsinntekter.sumDriftsinntekter"
        ),
        "driftsresultat": hent_nostet(
            regnskap, "resultatregnskapResultat.driftsresultat.driftsresultat"
        ),
        "ordinaert_res_foer_skatt": hent_nostet(
            regnskap, "resultatregnskapResultat.ordinaertResultatFoerSkattekostnad"
        ),
        "aarsresultat": hent_nostet(regnskap, "resultatregnskapResultat.aarsresultat"),
        "sum_eiendeler": sum_eiendeler,
        "sum_anleggsmidler": hent_nostet(regnskap, "eiendeler.anleggsmidler.sumAnleggsmidler"),
        "sum_omloepsmidler": hent_nostet(regnskap, "eiendeler.omloepsmidler.sumOmloepsmidler"),
        "sum_egenkapital": sum_ek,
        "sum_innskutt_ek": hent_nostet(
            regnskap, "egenkapitalGjeld.egenkapital.innskuttEgenkapital.sumInnskuttEgenkaptial"
        ),
        "sum_opptjent_ek": hent_nostet(
            regnskap, "egenkapitalGjeld.egenkapital.opptjentEgenkapital.sumOpptjentEgenkapital"
        ),
        "sum_gjeld": sum_gjeld,
        "sum_kortsiktig_gjeld": hent_nostet(
            regnskap, "egenkapitalGjeld.gjeldOversikt.kortsiktigGjeld.sumKortsiktigGjeld"
        ),
        "sum_langsiktig_gjeld": hent_nostet(
            regnskap, "egenkapitalGjeld.gjeldOversikt.langsiktigGjeld.sumLangsiktigGjeld"
        ),
        "sum_egenkapital_gjeld": hent_nostet(regnskap, "egenkapitalGjeld.sumEgenkapitalGjeld"),
        "balanseavvik": balanseavvik,
        "flagg_balanseavvik": flagg,
        "raa": json.dumps(regnskap, ensure_ascii=False),
        "hentet_tid": hentet_tid,
    }


def _personnavn(person: dict[str, Any]) -> str | None:
    navn = person.get("navn") or {}
    deler = [navn.get("fornavn"), navn.get("mellomnavn"), navn.get("etternavn")]
    sammensatt = " ".join(del_ for del_ in deler if del_)
    return sammensatt or None


def roller_til_rader(
    orgnr: str,
    svar: dict[str, Any],
    snapshot_dato: dt.date,
    hentet_tid: dt.datetime,
) -> list[dict[str, Any]]:
    """Flater et roller-svar til rolle-rader (én per rolle i snapshotet)."""
    rader: list[dict[str, Any]] = []
    for gruppe in svar.get("rollegrupper", []):
        gruppekode = hent_nostet(gruppe, "type.kode") or "?"
        for rolle in gruppe.get("roller", []):
            person = rolle.get("person")
            enhet = rolle.get("enhet")
            enhet_navn = None
            if enhet and enhet.get("navn"):
                enhet_navn = " ".join(enhet["navn"])
            rader.append(
                {
                    "orgnr": orgnr,
                    "snapshot_dato": snapshot_dato,
                    "rollegruppe": gruppekode,
                    "rolletype": hent_nostet(rolle, "type.kode") or "?",
                    "rekkefolge": rolle.get("rekkefolge"),
                    "er_person": person is not None,
                    "person_navn": _personnavn(person) if person else None,
                    "person_foedselsdato": person.get("fodselsdato") if person else None,
                    "person_er_doed": person.get("erDoed") if person else None,
                    "enhet_orgnr": enhet.get("organisasjonsnummer") if enhet else None,
                    "enhet_navn": enhet_navn,
                    "fratraadt": rolle.get("fratraadt"),
                    "hentet_tid": hentet_tid,
                }
            )
    return rader
