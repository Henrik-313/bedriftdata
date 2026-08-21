"""Årsregnskap (PDF): tilgjengelige årganger og nedlasting på forespørsel."""

import felles
import plotly.express as px
import streamlit as st

from bedriftdata import brreg
from bedriftdata.http import PoliteClient

felles.krev_database()

st.title("📄 Årsregnskap (PDF)")
st.caption(
    "Komplette innsendte årsregnskap (med noter/årsberetning) kan lastes ned gratis fra "
    "Regnskapsregisteret. Basen inneholder kun metadata om tilgjengelige årganger – "
    "PDF-er hentes på forespørsel."
)

tilgjengelighet = felles.sporr(
    """
    SELECT u.gruppe, a.regnskapsaar, count(DISTINCT a.orgnr) AS antall
    FROM aarsregnskap_aar a JOIN utvalg u USING (orgnr)
    GROUP BY ALL ORDER BY u.gruppe, a.regnskapsaar
    """
)
if tilgjengelighet.empty:
    st.info("Ingen metadata i basen ennå. Kjør `uv run bedriftdata aarsregnskap`.")
    st.stop()

gruppestorrelser = felles.sporr("SELECT gruppe, count(*) AS n FROM utvalg GROUP BY 1")

statistikk = felles.sporr(
    """
    SELECT count(DISTINCT orgnr) AS med_pdf,
           count(*) * 1.0 / count(DISTINCT orgnr) AS aar_snitt,
           min(regnskapsaar) AS eldste
    FROM aarsregnskap_aar
    """
).iloc[0]
i_utvalget = int(gruppestorrelser["n"].sum())

kolonner = st.columns(4)
kolonner[0].metric("Selskaper med PDF", felles.tall(statistikk["med_pdf"]))
kolonner[1].metric("Andel av utvalget", felles.prosent(statistikk["med_pdf"] / i_utvalget))
kolonner[2].metric("Årganger per selskap", f"{statistikk['aar_snitt']:.1f}".replace(".", ","))
kolonner[3].metric("Eldste årgang", int(statistikk["eldste"]))

st.subheader("Tilgjengelighet per gruppe og år")
matrise = (
    tilgjengelighet.merge(gruppestorrelser, on="gruppe")
    .assign(andel=lambda df: df["antall"] / df["n"])
    .pivot(index="gruppe", columns="regnskapsaar", values="andel")
    .sort_index()
)
fig = px.imshow(
    matrise,
    aspect="auto",
    color_continuous_scale="Blues",
    labels={"x": "Regnskapsår", "y": None, "color": "Andel med PDF"},
)
fig.update_coloraxes(cmin=0, cmax=1)
st.plotly_chart(fig)
st.caption(
    "Andel av selskapene i hver gruppe som har innsendt årsregnskap tilgjengelig som PDF. "
    "Lav dekning bakover i tid skyldes i hovedsak at selskapene er yngre enn arkivet."
)

st.subheader("Last ned et årsregnskap")
selskaper = felles.sporr(
    """
    SELECT u.orgnr, coalesce(e.navn, u.orgnr) AS navn
    FROM utvalg u
    JOIN aarsregnskap_aar a USING (orgnr)
    LEFT JOIN enhet e USING (orgnr)
    GROUP BY ALL ORDER BY navn
    """
)
valgt = st.selectbox(
    "Selskap",
    list(selskaper.itertuples(index=False)),
    format_func=lambda rad: f"{rad.navn} ({rad.orgnr})",
)
if valgt is not None:
    aar_liste = felles.sporr(
        "SELECT regnskapsaar FROM aarsregnskap_aar WHERE orgnr = ? ORDER BY 1 DESC",
        (valgt.orgnr,),
    )
    aar = st.selectbox("Regnskapsår", aar_liste["regnskapsaar"])
    if st.button("Hent PDF fra Regnskapsregisteret"):
        with st.spinner("Genereres hos Brønnøysund – store rapporter kan ta over ett minutt ..."):
            try:
                with PoliteClient() as klient:
                    pdf = brreg.hent_aarsregnskap_pdf(klient, valgt.orgnr, str(aar))
            except Exception as feil:  # noqa: BLE001 - vis alle feil pent i UI
                st.error(f"Nedlastingen feilet: {feil}")
                pdf = None
        if pdf is None:
            st.warning("Fant ingen PDF for dette året.")
        else:
            st.session_state["pdf_nedlasting"] = {
                "data": pdf,
                "filnavn": f"aarsregnskap_{valgt.orgnr}_{aar}.pdf",
            }
    nedlasting = st.session_state.get("pdf_nedlasting")
    if nedlasting:
        st.download_button(
            f"Lagre {nedlasting['filnavn']} ({len(nedlasting['data']) / 1_048_576:.1f} MB)",
            data=nedlasting["data"],
            file_name=nedlasting["filnavn"],
            mime="application/pdf",
        )
