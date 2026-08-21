"""Tester for transform.py. Alle fixtures er syntetiske – aldri ekte persondata."""

import datetime as dt

from bedriftdata.transform import regnskap_til_rad, roller_til_rader

HENTET = dt.datetime(2026, 8, 21, 12, 0, tzinfo=dt.UTC)


def lag_regnskap(eiendeler: float, egenkapital: float, gjeld: float) -> dict:
    return {
        "id": 123,
        "journalnr": "2026000001",
        "regnskapstype": "SELSKAP",
        "virksomhet": {"organisasjonsnummer": "999999999", "morselskap": False},
        "regnskapsperiode": {"fraDato": "2025-01-01", "tilDato": "2025-12-31"},
        "valuta": "NOK",
        "oppstillingsplan": "store",
        "avviklingsregnskap": False,
        "revisjon": {"ikkeRevidertAarsregnskap": False, "fravalgRevisjon": True},
        # API-ets faktiske (feilstavede) nøkler:
        "regnkapsprinsipper": {
            "smaaForetak": True,
            "regnskapsregler": "regnskapslovenAlminneligRegler",
        },
        "egenkapitalGjeld": {
            "sumEgenkapitalGjeld": egenkapital + gjeld,
            "egenkapital": {
                "sumEgenkapital": egenkapital,
                "innskuttEgenkapital": {"sumInnskuttEgenkaptial": 30_000.0},
                "opptjentEgenkapital": {"sumOpptjentEgenkapital": egenkapital - 30_000.0},
            },
            "gjeldOversikt": {
                "sumGjeld": gjeld,
                "kortsiktigGjeld": {"sumKortsiktigGjeld": gjeld},
            },
        },
        "eiendeler": {
            "sumEiendeler": eiendeler,
            "omloepsmidler": {"sumOmloepsmidler": eiendeler},
        },
        "resultatregnskapResultat": {
            "aarsresultat": 50_000.0,
            "ordinaertResultatFoerSkattekostnad": 64_000.0,
            "driftsresultat": {
                "driftsresultat": 70_000.0,
                "driftsinntekter": {"sumDriftsinntekter": 1_000_000.0},
                "driftskostnad": {"sumDriftskostnad": 930_000.0},
            },
        },
    }


def test_regnskap_til_rad_flater_ut_feilstavede_nokler():
    rad = regnskap_til_rad("999999999", lag_regnskap(1_000_000, 400_000, 600_000), HENTET)
    assert rad["orgnr"] == "999999999"
    assert rad["regnskapsaar"] == 2025
    assert rad["smaa_foretak"] is True
    assert rad["regnskapsregler"] == "regnskapslovenAlminneligRegler"
    assert rad["sum_innskutt_ek"] == 30_000.0
    assert rad["sum_driftsinntekter"] == 1_000_000.0
    assert rad["sum_eiendeler"] == 1_000_000.0
    assert rad["balanseavvik"] == 0.0
    assert rad["flagg_balanseavvik"] is False
    assert '"regnkapsprinsipper"' in rad["raa"]


def test_balanseflagg_slaar_ved_materielt_avvik():
    # 0,2 % avvik: eiendeler 1 000 000, EK+gjeld 998 000
    rad = regnskap_til_rad("999999999", lag_regnskap(1_000_000, 400_000, 598_000), HENTET)
    assert rad["balanseavvik"] == 2_000.0
    assert rad["flagg_balanseavvik"] is True


def test_balanseflagg_ignorerer_avrunding():
    # 0,05 % avvik skal ikke flagges
    rad = regnskap_til_rad("999999999", lag_regnskap(1_000_000, 400_000, 599_500), HENTET)
    assert rad["flagg_balanseavvik"] is False


def test_regnskap_uten_balansetall_faar_ikke_flagg():
    regnskap = lag_regnskap(1_000_000, 400_000, 600_000)
    del regnskap["egenkapitalGjeld"]["gjeldOversikt"]
    rad = regnskap_til_rad("999999999", regnskap, HENTET)
    assert rad["sum_gjeld"] is None
    assert rad["balanseavvik"] is None
    assert rad["flagg_balanseavvik"] is False


ROLLER_SVAR = {
    "rollegrupper": [
        {
            "type": {"kode": "STYR", "beskrivelse": "Styre"},
            "roller": [
                {
                    "type": {"kode": "LEDE", "beskrivelse": "Styrets leder"},
                    "person": {
                        "navn": {"fornavn": "Kari", "etternavn": "Testperson"},
                        "fodselsdato": "1980-01-15",
                        "erDoed": False,
                    },
                    "fratraadt": False,
                    "rekkefolge": 1,
                },
                {
                    # juridisk enhet som rolleinnehaver, uten rekkefolge
                    "type": {"kode": "MEDL", "beskrivelse": "Styremedlem"},
                    "enhet": {
                        "organisasjonsnummer": "888888888",
                        "navn": ["TESTSELSKAP", "HOLDING AS"],
                        "erSlettet": False,
                    },
                    "fratraadt": False,
                },
            ],
        },
        {
            "type": {"kode": "DAGL", "beskrivelse": "Daglig leder"},
            "roller": [
                {
                    "type": {"kode": "DAGL", "beskrivelse": "Daglig leder"},
                    "person": {
                        "navn": {
                            "fornavn": "Ola",
                            "mellomnavn": "Fiktiv",
                            "etternavn": "Testperson",
                        },
                        "fodselsdato": "1975-06-01",
                        "erDoed": False,
                    },
                    "fratraadt": False,
                    "rekkefolge": 1,
                }
            ],
        },
    ]
}


def test_roller_til_rader_person_og_enhet():
    rader = roller_til_rader("999999999", ROLLER_SVAR, dt.date(2026, 8, 21), HENTET)
    assert len(rader) == 3

    leder = rader[0]
    assert leder["rollegruppe"] == "STYR"
    assert leder["rolletype"] == "LEDE"
    assert leder["er_person"] is True
    assert leder["person_navn"] == "Kari Testperson"
    assert leder["enhet_orgnr"] is None

    juridisk = rader[1]
    assert juridisk["er_person"] is False
    assert juridisk["enhet_orgnr"] == "888888888"
    assert juridisk["enhet_navn"] == "TESTSELSKAP HOLDING AS"
    assert juridisk["rekkefolge"] is None
    assert juridisk["person_navn"] is None

    daglig = rader[2]
    assert daglig["person_navn"] == "Ola Fiktiv Testperson"


def test_roller_tomt_svar():
    assert roller_til_rader("999999999", {}, dt.date(2026, 8, 21), HENTET) == []
