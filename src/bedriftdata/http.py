"""Enkel, høflig HTTP-klient for utforskning av åpne API-er.

Holder forespørselsraten nede og prøver på nytt ved 429/5xx, slik at vi
oppfører oss pent mot offentlige API-er under utforskningen.
"""

from __future__ import annotations

import time
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
        self, url: str, params: dict[str, Any] | None = None, max_forsok: int = 4
    ) -> httpx.Response:
        siste_respons: httpx.Response | None = None
        siste_feil: Exception | None = None
        for forsok in range(max_forsok):
            self._vent()
            try:
                respons = self._client.get(url, params=params)
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
