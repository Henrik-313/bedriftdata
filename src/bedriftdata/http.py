"""Enkel, høflig HTTP-klient for utforskning av åpne API-er.

Holder forespørselsraten nede og prøver på nytt ved 429/5xx, slik at vi
oppfører oss pent mot offentlige API-er under utforskningen.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import httpx

DEFAULT_USER_AGENT = "bedriftdata-utforskning/0.1 (personlig datautforskning; Python httpx)"

RETRY_STATUSER = {429, 500, 502, 503, 504}


class PoliteClient:
    """GET-klient med rate-limiting og enkel retry med backoff."""

    def __init__(
        self,
        requests_per_second: float = 4.0,
        timeout: float = 30.0,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._min_interval = 1.0 / requests_per_second
        self._forrige_kall = 0.0
        alle_headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "application/json"}
        if headers:
            alle_headers.update(headers)
        self._client = httpx.Client(timeout=timeout, headers=alle_headers, follow_redirects=True)

    def _vent(self) -> None:
        ventetid = self._min_interval - (time.monotonic() - self._forrige_kall)
        if ventetid > 0:
            time.sleep(ventetid)
        self._forrige_kall = time.monotonic()

    def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        max_forsok: int = 4,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> httpx.Response:
        siste_respons: httpx.Response | None = None
        siste_feil: Exception | None = None
        for forsok in range(max_forsok):
            self._vent()
            try:
                respons = self._client.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=timeout if timeout is not None else httpx.USE_CLIENT_DEFAULT,
                )
            except httpx.TransportError as feil:
                siste_feil = feil
            else:
                if respons.status_code not in RETRY_STATUSER:
                    return respons
                siste_respons = respons
                siste_feil = None
            if forsok < max_forsok - 1:
                time.sleep(2**forsok)
        if siste_respons is not None:
            return siste_respons
        raise siste_feil  # type: ignore[misc]  # alle forsøk ga transportfeil

    def last_ned_fil(
        self,
        url: str,
        mal_sti: Path,
        timeout: float = 900.0,
        headers: dict[str, str] | None = None,
    ) -> int:
        """Laster ned en (potensielt stor) fil strømmende til disk. Returnerer antall byte.

        Skriver til en midlertidig fil og bytter inn til slutt, så en avbrutt
        nedlasting aldri etterlater en halv fil på målstien.
        """
        from tqdm import tqdm

        self._vent()
        mal_sti.parent.mkdir(parents=True, exist_ok=True)
        tmp_sti = mal_sti.with_suffix(mal_sti.suffix + ".del")
        alle_headers = {"Accept": "*/*", **(headers or {})}
        with self._client.stream("GET", url, headers=alle_headers, timeout=timeout) as respons:
            respons.raise_for_status()
            total = int(respons.headers.get("content-length", 0)) or None
            med_progresjon = tqdm(
                total=total, unit="B", unit_scale=True, desc=mal_sti.name, leave=False
            )
            with open(tmp_sti, "wb") as fil, med_progresjon as progresjon:
                for bit in respons.iter_bytes(chunk_size=1 << 20):
                    fil.write(bit)
                    progresjon.update(len(bit))
        tmp_sti.replace(mal_sti)
        return mal_sti.stat().st_size

    def get_json(self, url: str, params: dict[str, Any] | None = None) -> Any | None:
        """Henter JSON. Returnerer None ved 404/410 (ressurs finnes ikke)."""
        respons = self.get(url, params=params)
        if respons.status_code in (404, 410):
            return None
        respons.raise_for_status()
        return respons.json()

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> PoliteClient:
        return self

    def __exit__(self, *_: object) -> None:
        self.close()
