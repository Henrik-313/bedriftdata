"""Regnskap: dekning, fordelinger og kvalitetsflagg for høsteutvalget."""

import felles
import plotly.express as px
import streamlit as st

felles.krev_database()

st.title("📈 Regnskap")
st.caption(
    "Nøkkeltall fra det åpne regnskaps-API-et for selskapene i høsteutvalget. "
    "API-et gir kun siste innsendte år – historikk bygges over tid."
)

regnskap = felles.sporr("SELECT * FROM v_regnskap_kvalitet")
if regnskap.empty:
    st.info("Ingen regnskap i basen ennå. Kjør `uv run bedriftdata regnskap`.")
    st.stop()

dekning = felles.sporr(
    """
    SELECT count(*) AS i_utvalget,
           avg(CASE WHEN h.status = 'ok' THEN 1.0 ELSE 0.0 END) AS andel_ok,
           sum(CASE WHEN h.permanent_feil THEN 1 ELSE 0 END) AS permanente_feil
    FROM utvalg u
    LEFT JOIN hentestatus h ON h.kilde = 'regnskap' AND h.orgnr = u.orgnr
    """
).iloc[0]

kolonner = st.columns(5)
kolonner[0].metric("Regnskap i basen", felles.tall(len(regnskap)))
kolonner[1].metric("Dekning i utvalget", felles.prosent(dekning["andel_ok"]))
kolonner[2].metric("Permanente feil", felles.tall(dekning["permanente_feil"]))
kolonner[3].metric(
    "Med balanseavvik-flagg",
    felles.prosent(regnskap["flagg_balanseavvik"].fillna(False).mean()),
)
kolonner[4].metric("Ikke-NOK", felles.prosent((regnskap["valuta"] != "NOK").mean()))

venstre, hoyre = st.columns(2)

with venstre:
    st.subheader("Hentestatus per gruppe")
    status = felles.sporr(
        """
        SELECT u.gruppe,
               coalesce(CASE WHEN h.permanent_feil THEN 'permanent feil' ELSE h.status END,
                        'ikke forsøkt') AS status,
               count(*) AS antall
        FROM utvalg u
        LEFT JOIN hentestatus h ON h.kilde = 'regnskap' AND h.orgnr = u.orgnr
        GROUP BY ALL ORDER BY u.gruppe
        """
    )
    fig = px.bar(status, x="gruppe", y="antall", color="status")
    fig.update_layout(xaxis_title=None, yaxis_title="Antall selskaper")
    st.plotly_chart(fig)

    st.subheader("Driftsinntekter (størrelsesorden)")
    omsetning = felles.sporr(
        """
        SELECT cast(floor(log10(sum_driftsinntekter)) AS INTEGER) AS mag, count(*) AS antall
        FROM regnskap WHERE sum_driftsinntekter > 0
        GROUP BY 1 ORDER BY 1
        """
    )
    etiketter = {
        0: "1–10", 1: "10–100", 2: "0,1–1 k", 3: "1–10 k", 4: "10–100 k",
        5: "0,1–1 mill.", 6: "1–10 mill.", 7: "10–100 mill.", 8: "0,1–1 mrd.",
        9: "1–10 mrd.", 10: "10–100 mrd.", 11: "100–1000 mrd.",
    }  # fmt: skip
    omsetning["intervall"] = omsetning["mag"].map(lambda m: etiketter.get(m, f"10^{m}") + " kr")
    fig = px.bar(omsetning, x="intervall", y="antall")
    fig.update_layout(xaxis_title="Driftsinntekter", yaxis_title="Antall selskaper")
    st.plotly_chart(fig)

    st.subheader("Egenkapitalandel")
    ek = regnskap.dropna(subset=["sum_egenkapital", "sum_eiendeler"])
    ek = ek[ek["sum_eiendeler"] > 0]
    ek_andel = (ek["sum_egenkapital"] / ek["sum_eiendeler"]).clip(-1, 1.5)
    fig = px.histogram(ek_andel, nbins=50)
    fig.update_layout(
        xaxis_title="Egenkapital / eiendeler (klippet til [-1, 1,5])",
        yaxis_title="Antall selskaper",
        showlegend=False,
    )
    st.plotly_chart(fig)

with hoyre:
    st.subheader("Regnskapsår (ferskhet)")
    aar = felles.sporr(
        "SELECT regnskapsaar, count(*) AS antall FROM regnskap GROUP BY 1 ORDER BY 1"
    )
    fig = px.bar(aar, x="regnskapsaar", y="antall")
    fig.update_layout(xaxis_title="Regnskapsår", yaxis_title="Antall regnskap")
    st.plotly_chart(fig)

    st.subheader("Årsresultat (størrelsesorden, med fortegn)")
    resultat = felles.sporr(
        """
        SELECT CASE WHEN aarsresultat >= 0 THEN 1 ELSE -1 END
               * cast(floor(log10(greatest(abs(aarsresultat), 1))) AS INTEGER) AS mag,
               count(*) AS antall
        FROM regnskap WHERE aarsresultat IS NOT NULL AND abs(aarsresultat) >= 1000
        GROUP BY 1 ORDER BY 1
        """
    )
    fig = px.bar(resultat, x="mag", y="antall")
    fig.update_layout(
        xaxis_title="log10(|årsresultat|) · fortegn (negativt = underskudd)",
        yaxis_title="Antall selskaper",
    )
    st.plotly_chart(fig)

    st.subheader("Valuta og regnskapsregler")
    valuta_kolonne, regler_kolonne = st.columns(2)
    valuta = regnskap["valuta"].value_counts().reset_index()
    fig = px.pie(valuta, names="valuta", values="count", hole=0.5)
    valuta_kolonne.plotly_chart(fig)
    regler = regnskap["regnskapsregler"].value_counts().reset_index()
    fig = px.pie(regler, names="regnskapsregler", values="count", hole=0.5)
    regler_kolonne.plotly_chart(fig)

st.subheader("Kvalitetsflagg")
flagget = regnskap[regnskap["flagg_balanseavvik"].fillna(False)]
if flagget.empty:
    st.success("Ingen regnskap med materielt balanseavvik i basen.")
else:
    st.caption(
        "Regnskap der eiendeler ≠ egenkapital + gjeld med mer enn 0,1 % av balansesummen. "
        "Bruk `sum_eiendeler` som balansesum for disse – gjeldsaggregatene i API-et kan "
        "mangle poster."
    )
    vis = flagget[
        ["orgnr", "navn", "gruppe", "regnskapsaar", "sum_eiendeler", "balanseavvik", "valuta"]
    ].sort_values("balanseavvik", key=abs, ascending=False)
    st.dataframe(vis, hide_index=True)

feilede = felles.sporr(
    "SELECT h.orgnr, e.navn, e.naeringskode1, h.feilmelding"
    " FROM hentestatus h LEFT JOIN enhet e USING (orgnr)"
    " WHERE h.kilde = 'regnskap' AND h.permanent_feil ORDER BY e.navn"
)
if not feilede.empty:
    with st.expander(f"Selskaper uten regnskap i det åpne API-et ({len(feilede)})"):
        st.caption(
            "I hovedsak banker og forsikringsforetak – API-et støtter ikke "
            "oppstillingsplanene deres."
        )
        st.dataframe(feilede, hide_index=True)
