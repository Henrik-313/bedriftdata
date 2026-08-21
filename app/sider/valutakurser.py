"""Valutakurser fra Norges Bank: seriene som brukes til NOK-normalisering."""

import felles
import plotly.express as px
import streamlit as st

felles.krev_database()

st.title("💱 Valutakurser")
st.caption("Daglige midtkurser fra Norges Bank, i NOK per 1 enhet valuta.")

tilgjengelige = felles.sporr("SELECT DISTINCT valuta FROM valutakurs ORDER BY 1")
if tilgjengelige.empty:
    st.info("Ingen kurser i basen ennå. Kjør `uv run bedriftdata valutakurser`.")
    st.stop()

siste = felles.sporr(
    """
    SELECT valuta, arg_max(kurs_nok, dato) AS kurs, max(dato) AS dato
    FROM valutakurs GROUP BY 1 ORDER BY 1
    """
)
kolonner = st.columns(len(siste))
for kolonne, rad in zip(kolonner, siste.itertuples(index=False), strict=False):
    kolonne.metric(rad.valuta, f"{rad.kurs:.2f}".replace(".", ","))

standard = [valuta for valuta in ("USD", "EUR") if valuta in set(tilgjengelige["valuta"])]
valgte = st.multiselect("Valutaer", tilgjengelige["valuta"], default=standard)

aarsspenn = felles.sporr("SELECT year(min(dato)) AS fra, year(max(dato)) AS til FROM valutakurs")
fra_aar, til_aar = int(aarsspenn["fra"][0]), int(aarsspenn["til"][0])
valgt_spenn = st.slider("Årsintervall", fra_aar, til_aar, (fra_aar, til_aar))

if valgte:
    plassholdere = ", ".join("?" for _ in valgte)
    kurser = felles.sporr(
        f"SELECT valuta, dato, kurs_nok FROM valutakurs"
        f" WHERE valuta IN ({plassholdere}) AND year(dato) BETWEEN ? AND ?"
        f" ORDER BY dato",
        (*valgte, valgt_spenn[0], valgt_spenn[1]),
    )
    fig = px.line(kurser, x="dato", y="kurs_nok", color="valuta")
    fig.update_layout(xaxis_title=None, yaxis_title="NOK per enhet")
    st.plotly_chart(fig)

oppdatert = felles.sporr("SELECT max(hentet_tid) AS tid FROM valutakurs")
st.caption(f"Sist hentet: {felles.til_oslo_tid(oppdatert['tid'])[0]} (kilde: Norges Bank)")
