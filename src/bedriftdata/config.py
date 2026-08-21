"""Laster config.toml til typede konfigobjekter."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from bedriftdata.utils import PROSJEKTROT

STANDARD_KONFIGSTI = PROSJEKTROT / "config.toml"


@dataclass(frozen=True)
class UtvalgsRegel:
    navn: str
    orgform: str
    ansatte_min: int | None = None
    ansatte_max: int | None = None
    antall: int | None = None  # None = alle treff


@dataclass(frozen=True)
class Konfig:
    db_sti: Path
    friskhet_dager: int = 30
    requests_per_second: float = 4.0
    valutaer: list[str] = field(default_factory=list)
    valuta_start_aar: int = 2014
    utvalgsregler: list[UtvalgsRegel] = field(default_factory=list)


def last_konfig(sti: Path | None = None) -> Konfig:
    sti = sti or STANDARD_KONFIGSTI
    data = tomllib.loads(sti.read_text(encoding="utf-8"))

    db_sti = Path(data["lagring"]["db_sti"])
    if not db_sti.is_absolute():
        db_sti = PROSJEKTROT / db_sti

    hosting = data.get("hosting", {})
    valuta = data.get("valutakurser", {})
    regler = [
        UtvalgsRegel(
            navn=regel["navn"],
            orgform=regel["orgform"],
            ansatte_min=regel.get("ansatte_min"),
            ansatte_max=regel.get("ansatte_max"),
            antall=regel.get("antall"),
        )
        for regel in data.get("utvalg", {}).get("regler", [])
    ]
    return Konfig(
        db_sti=db_sti,
        friskhet_dager=int(hosting.get("friskhet_dager", 30)),
        requests_per_second=float(hosting.get("requests_per_second", 4.0)),
        valutaer=list(valuta.get("valutaer", [])),
        valuta_start_aar=int(valuta.get("start_aar", 2014)),
        utvalgsregler=regler,
    )
