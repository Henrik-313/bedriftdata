"""Roller: aggregert statistikk over styrer, ledelse og revisorer i utvalget."""

import felles
import plotly.express as px
import streamlit as st

felles.krev_database()

st.title("👥 Roller")
st.info(
    "Rolledata inneholder personopplysninger (navn og fødselsdato). "
    "Denne siden viser kun aggregater, og basen skal ikke deles eller publiseres.",
    icon="🔒",
)

snapshots = felles.sporr("SELECT DISTINCT snapshot_dato FROM rolle ORDER BY 1 DESC")
if snapshots.empty:
    st.info("Ingen roller i basen ennå. Kjør `uv run bedriftdata roller`.")
    st.stop()

snapshot = st.selectbox("Snapshot-dato", snapshots["snapshot_dato"])

kolonner = st.columns(4)
totaler = felles.sporr(
    "SELECT count(*) AS roller, count(DISTINCT orgnr) AS selskaper,"
    " avg(CASE WHEN er_person THEN 1.0 ELSE 0.0 END) AS andel_person,"
    " avg(CASE WHEN fratraadt THEN 1.0 ELSE 0.0 END) AS andel_fratraadt"
    " FROM rolle WHERE snapshot_dato = ?",
    (snapshot,),
).iloc[0]
kolonner[0].metric("Roller", felles.tall(totaler["roller"]))
kolonner[1].metric("Selskaper med roller", felles.tall(totaler["selskaper"]))
kolonner[2].metric("Holdt av person", felles.prosent(totaler["andel_person"]))
kolonner[3].metric("Fratrådt", felles.prosent(totaler["andel_fratraadt"]))

venstre, hoyre = st.columns(2)

with venstre:
    st.subheader("Rolletyper")
    rolletyper = felles.sporr(
        "SELECT rollegruppe, rolletype, count(*) AS antall FROM rolle"
        " WHERE snapshot_dato = ? GROUP BY ALL ORDER BY antall DESC",
        (snapshot,),
    )
    fig = px.bar(
        rolletyper.sort_values("antall"),
        x="antall",
        y="rolletype",
        color="rollegruppe",
        orientation="h",
    )
    fig.update_layout(xaxis_title="Antall roller", yaxis_title=None)
    st.plotly_chart(fig)

    st.subheader("Person vs. juridisk enhet")
    innehavere = felles.sporr(
        "SELECT CASE WHEN er_person THEN 'Person' ELSE 'Juridisk enhet' END AS type,"
        " count(*) AS antall FROM rolle WHERE snapshot_dato = ? GROUP BY 1",
        (snapshot,),
    )
    fig = px.pie(innehavere, names="type", values="antall", hole=0.5)
    st.plotly_chart(fig)

with hoyre:
    st.subheader("Styrestørrelse (uten varamedlemmer)")
    styrer = felles.sporr(
        """
        SELECT antall_medlemmer, count(*) AS antall_selskaper
        FROM (
            SELECT orgnr, count(*) AS antall_medlemmer
            FROM rolle
            WHERE snapshot_dato = ? AND rollegruppe = 'STYR' AND rolletype != 'VARA'
            GROUP BY orgnr
        )
        GROUP BY 1 ORDER BY 1
        """,
        (snapshot,),
    )
    fig = px.bar(styrer, x="antall_medlemmer", y="antall_selskaper")
    fig.update_layout(xaxis_title="Antall styremedlemmer", yaxis_title="Antall selskaper")
    st.plotly_chart(fig)

    st.subheader("Roller per selskap, etter gruppe")
    per_gruppe = felles.sporr(
        """
        SELECT u.gruppe, count(*) * 1.0 / count(DISTINCT r.orgnr) AS snitt
        FROM rolle r JOIN utvalg u USING (orgnr)
        WHERE r.snapshot_dato = ? GROUP BY 1 ORDER BY 1
        """,
        (snapshot,),
    )
    fig = px.bar(per_gruppe, x="gruppe", y="snitt")
    fig.update_layout(xaxis_title=None, yaxis_title="Gjennomsnittlig antall roller")
    st.plotly_chart(fig)

st.caption(
    "Rollegrupper: STYR = styre, DAGL = daglig leder, REVI = revisor, REGN = regnskapsfører, "
    "INNH = innehaver, KONT = kontaktperson, REPR = norsk representant (NUF)."
)
