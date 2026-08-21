"""Hjelpefunksjoner for utforskningsskriptene."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

PROSJEKTROT = Path(__file__).resolve().parents[2]
DATA_RAW = PROSJEKTROT / "data" / "raw"
DATA_SAMPLES = PROSJEKTROT / "data" / "samples"


def sikre_datamapper() -> None:
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    DATA_SAMPLES.mkdir(parents=True, exist_ok=True)


def lagre_json(obj: Any, sti: Path) -> None:
    sti.parent.mkdir(parents=True, exist_ok=True)
    sti.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")


def flat_nokler(obj: Any, prefiks: str = "") -> set[str]:
    """Alle nøkkelstier i en nøstet JSON-struktur, med `[]` for lister.

    Brukes til å kartlegge hvilke felter som faktisk finnes i API-svarene.
    """
    stier: set[str] = set()
    if isinstance(obj, dict):
        for nokkel, verdi in obj.items():
            sti = f"{prefiks}.{nokkel}" if prefiks else nokkel
            understier = flat_nokler(verdi, sti)
            stier.update(understier if understier else {sti})
    elif isinstance(obj, list):
        for element in obj:
            stier.update(flat_nokler(element, f"{prefiks}[]"))
        if not obj:
            stier.add(f"{prefiks}[]")
    else:
        if prefiks:
            stier.add(prefiks)
    return stier


def feltdekning(objekter: list[Any]) -> Counter[str]:
    """Teller hvor mange objekter som inneholder hver nøkkelsti."""
    teller: Counter[str] = Counter()
    for obj in objekter:
        for sti in flat_nokler(obj):
            teller[sti] += 1
    return teller


def hent_nostet(obj: Any, sti: str, standard: Any = None) -> Any:
    """Slår opp en punktum-separert sti i nøstede dicts, f.eks. 'eiendeler.sumEiendeler'."""
    for del_ in sti.split("."):
        if not isinstance(obj, dict) or del_ not in obj:
            return standard
        obj = obj[del_]
    return obj
