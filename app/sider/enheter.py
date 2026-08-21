"""Enhetsregisteret: deskriptiv statistikk over hele bestanden (~1,1 mill. enheter).

All aggregering skjer i SQL – pandas får kun ferdige aggregater.
"""

import felles
import plotly.express as px
import streamlit as st

felles.krev_database()

st.title("🏢 Enhetsregisteret")

totaler = felles.sporr(
    "SELECT count(*) AS antall,"
    " avg(CASE WHEN konkurs THEN 1.0 ELSE 0.0 END) AS andel_konkurs,"
    " avg(CASE WHEN under_avvikling THEN 1.0 ELSE 0.0 END) AS andel_avvikling,"
    " avg(CASE WHEN under_tvangsavvikling THEN 1.0 ELSE 0.0 END) AS andel_tvang,"
    " avg(CASE WHEN har_ansatte_reg THEN 1.0 ELSE 0.0 END) AS andel_med_ansatte"
    " FROM enhet"
).iloc[0]

kolonner = st.columns(5)
kolonner[0].metric("Registrerte enheter", felles.tall(totaler["antall"]))
kolonner[1].metric("Med registrerte ansatte", felles.prosent(totaler["andel_med_ansatte"]))
kolonner[2].metric("Konkurs", felles.prosent(totaler["andel_konkurs"], 2))
kolonner[3].metric("Under avvikling", felles.prosent(totaler["andel_avvikling"], 2))
kolonner[4].metric("Under tvangsavvikling", felles.prosent(totaler["andel_tvang"], 2))

venstre, hoyre = st.columns(2)

with venstre:
    st.subheader("Organisasjonsformer")
    orgformer = felles.sporr(
        "SELECT orgform, count(*) AS antall FROM enhet GROUP BY 1 ORDER BY 2 DESC LIMIT 15"
    )
    fig = px.bar(orgformer.sort_values("antall"), x="antall", y="orgform", orientation="h")
    fig.update_layout(xaxis_title="Antall enheter", yaxis_title=None)
    st.plotly_chart(fig)

    st.subheader("Fylker")
    fylker = felles.sporr(
        "SELECT fylke, count(*) AS antall FROM v_enhet_fylke GROUP BY 1 ORDER BY 2 DESC"
    )
    fig = px.bar(fylker.sort_values("antall"), x="antall", y="fylke", orientation="h")
    fig.update_layout(xaxis_title="Antall enheter", yaxis_title=None)
    st.plotly_chart(fig)

    st.subheader("Alder (fra stiftelsesdato)")
    alder = felles.sporr(
        """
        SELECT bucket, min(sortering) AS sortering, count(*) AS antall
        FROM (
            SELECT CASE
                WHEN stiftelsesdato IS NULL THEN 'ukjent'
                WHEN alder < 2 THEN '0–1 år'
                WHEN alder < 5 THEN '2–4 år'
                WHEN alder < 10 THEN '5–9 år'
                WHEN alder < 20 THEN '10–19 år'
                WHEN alder < 50 THEN '20–49 år'
                ELSE '50+ år' END AS bucket,
            CASE
                WHEN stiftelsesdato IS NULL THEN 99
                WHEN alder < 2 THEN 0 WHEN alder < 5 THEN 1 WHEN alder < 10 THEN 2
                WHEN alder < 20 THEN 3 WHEN alder < 50 THEN 4 ELSE 5 END AS sortering
            FROM (SELECT date_diff('year', stiftelsesdato, current_date) AS alder,
                         stiftelsesdato FROM enhet)
        )
        GROUP BY bucket ORDER BY sortering
        """
    )
    fig = px.bar(alder, x="bucket", y="antall")
    fig.update_layout(xaxis_title=None, yaxis_title="Antall enheter")
    st.plotly_chart(fig)

with hoyre:
    st.subheader("Næringer (NACE 2-siffer, topp 20)")
    naeringer = felles.sporr(
        "SELECT substr(naeringskode1, 1, 2) AS nace, count(*) AS antall,"
        " min(naering1_beskrivelse) AS eksempel"
        " FROM enhet WHERE naeringskode1 IS NOT NULL"
        " GROUP BY 1 ORDER BY 2 DESC LIMIT 20"
    )
    fig = px.bar(
        naeringer.sort_values("antall"),
        x="antall",
        y="nace",
        orientation="h",
        hover_data={"eksempel": True},
    )
    # NACE-kodene er sifferstrenger – uten dette tolker plotly aksen numerisk
    fig.update_yaxes(type="category")
    fig.update_layout(xaxis_title="Antall enheter", yaxis_title="NACE 2-siffer")
    st.plotly_chart(fig)

    st.subheader("Ansatte (der de er registrert)")
    ansatte = felles.sporr(
        """
        SELECT bucket, min(sortering) AS sortering, count(*) AS antall
        FROM (
            SELECT CASE
                WHEN antall_ansatte >= 250 THEN '250+'
                WHEN antall_ansatte >= 50 THEN '50–249'
                WHEN antall_ansatte >= 10 THEN '10–49'
                WHEN antall_ansatte >= 1 THEN '1–9'
                ELSE '0' END AS bucket,
            CASE
                WHEN antall_ansatte >= 250 THEN 4 WHEN antall_ansatte >= 50 THEN 3
                WHEN antall_ansatte >= 10 THEN 2 WHEN antall_ansatte >= 1 THEN 1
                ELSE 0 END AS sortering
            FROM enhet WHERE har_ansatte_reg
        )
        GROUP BY bucket ORDER BY sortering
        """
    )
    fig = px.bar(ansatte, x="bucket", y="antall")
    fig.update_layout(xaxis_title="Antall ansatte", yaxis_title="Antall enheter")
    st.plotly_chart(fig)
    st.caption(
        "Ansattetall finnes bare der arbeidsforhold er meldt til Aa-registeret – "
        "manglende tall betyr ikke nødvendigvis null ansatte."
    )

    st.subheader("Nyregistreringer per år")
    registreringer = felles.sporr(
        "SELECT year(registreringsdato) AS aar, count(*) AS antall"
        " FROM enhet WHERE registreringsdato IS NOT NULL AND year(registreringsdato) >= 1996"
        " GROUP BY 1 ORDER BY 1"
    )
    fig = px.line(registreringer, x="aar", y="antall")
    fig.update_layout(xaxis_title=None, yaxis_title="Nyregistrerte enheter")
    st.plotly_chart(fig)
    st.caption(
        "Registrert i Enhetsregisteret (opprettet 1995) – eldre virksomheter ble "
        "masseregistrert de første årene og er utelatt."
    )

st.subheader("Feltdekning")
felter = {
    "navn": "Navn",
    "orgform": "Organisasjonsform",
    "naeringskode1": "Næringskode",
    "sektorkode": "Sektorkode",
    "kommunenummer": "Kommunenummer",
    "stiftelsesdato": "Stiftelsesdato",
    "registreringsdato": "Registreringsdato",
    "siste_regnskapsaar": "Siste årsregnskap",
    "antall_ansatte": "Antall ansatte",
}
uttrykk = ", ".join(
    f"avg(CASE WHEN {kolonne} IS NOT NULL THEN 1.0 ELSE 0.0 END) AS {kolonne}" for kolonne in felter
)
dekning = (
    felles.sporr(f"SELECT {uttrykk} FROM enhet").T.reset_index().set_axis(["felt", "andel"], axis=1)
)
dekning["felt"] = dekning["felt"].map(felter)
fig = px.bar(dekning.sort_values("andel"), x="andel", y="felt", orientation="h")
fig.update_layout(
    xaxis_title="Andel enheter med feltet utfylt", yaxis_title=None, xaxis_tickformat=".0%"
)
st.plotly_chart(fig)
