"""Sjekker hva Proff.no tillater av automatisert tilgang (robots.txt).

Dette skriptet henter og arkiverer kun robots.txt – ingen skraping av innhold.
Vurdering av vilkår og alternativer ligger i docs/datakilder.md.

Kjør: uv run python explore/06_proff_robots.py
"""

from bedriftdata.http import PoliteClient
from bedriftdata.utils import DATA_RAW, sikre_datamapper


def main() -> None:
    sikre_datamapper()
    with PoliteClient(requests_per_second=1.0) as client:
        respons = client.get("https://www.proff.no/robots.txt")
    print(f"status: {respons.status_code}\n")
    print(respons.text)
    (DATA_RAW / "proff_robots.txt").write_text(respons.text, encoding="utf-8")
    print("\nLagret til data/raw/proff_robots.txt")


if __name__ == "__main__":
    main()
