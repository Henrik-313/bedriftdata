"""Oversiktsside: status, omfang og ferskhet for alle datakilder."""

import felles
import streamlit as st

felles.krev_database()

st.title("🏠 Oversikt")
st.caption("Status for datakildene i basen – hva som er hentet, når og hvor mye.")

oversikt = felles.sporr(
    "SELECT kilde, navn, beskrivelse, lisens, rader, dato_fra, dato_til,"
    " siste_status, siste_ferdig, siste_rader, siste_feil"
    " FROM v_kildeoversikt ORDER BY navn"
)
rader_per_kilde = dict(zip(oversikt["kilde"], oversikt["rader"], strict=False))

kolonner = st.columns(6)
metrikker = [
    ("Enheter", "enheter"),
    ("I utvalget", "utvalg"),
    ("Regnskap", "regnskap"),
    ("Rolle-rader", "roller"),
    ("PDF-årganger", "aarsregnskap_aar"),
    ("Valutakurser", "valutakurs"),
]
for kolonne, (navn, kilde) in zip(kolonner, metrikker, strict=False):
    kolonne.metric(navn, felles.tall(rader_per_kilde.get(kilde)))

st.subheader("Datakilder")
vis = oversikt.copy()
vis["siste_ferdig"] = felles.til_oslo_tid(vis["siste_ferdig"])
vis = vis.drop(columns=["kilde"]).rename(
    columns={
        "navn": "Kilde",
        "beskrivelse": "Beskrivelse",
        "lisens": "Lisens",
        "rader": "Rader",
        "dato_fra": "Data fra",
        "dato_til": "Data til",
        "siste_status": "Siste status",
        "siste_ferdig": "Sist innlastet",
        "siste_rader": "Rader sist",
        "siste_feil": "Feil sist",
    }
)
st.dataframe(vis, hide_index=True)

st.subheader("Siste kjøringer")
kjoringer = felles.sporr(
    "SELECT kilde, startet_tid, ferdig_tid, status, rader_skrevet, antall_feil"
    " FROM innlasting ORDER BY startet_tid DESC LIMIT 30"
)
if kjoringer.empty:
    st.info("Ingen innlastinger er kjørt ennå.")
else:
    kjoringer["startet_tid"] = felles.til_oslo_tid(kjoringer["startet_tid"])
    kjoringer["ferdig_tid"] = felles.til_oslo_tid(kjoringer["ferdig_tid"])
    kjoringer = kjoringer.rename(
        columns={
            "kilde": "Kilde",
            "startet_tid": "Startet",
            "ferdig_tid": "Ferdig",
            "status": "Status",
            "rader_skrevet": "Rader",
            "antall_feil": "Feil",
        }
    )
    st.dataframe(kjoringer, hide_index=True)

hentefeil = felles.sporr(
    "SELECT h.kilde, h.orgnr, e.navn, h.http_status, h.feilmelding"
    " FROM hentestatus h LEFT JOIN enhet e USING (orgnr)"
    " WHERE h.permanent_feil ORDER BY h.kilde, h.orgnr"
)
if not hentefeil.empty:
    with st.expander(f"Kjente permanente hentefeil ({len(hentefeil)})"):
        st.dataframe(hentefeil, hide_index=True)

st.divider()
st.caption(
    "Inneholder data under Norsk lisens for offentlige data (NLOD) tilgjengeliggjort av "
    "Brønnøysundregistrene, og valutakurser fra Norges Bank. "
    "Rolledata inneholder personopplysninger (navn og fødselsdato) og er kun til privat bruk – "
    "ikke publiser eller del basen."
)
