"""Dashbord for bedriftdata-basen. Kjør: uv run streamlit run app/dashboard.py"""

import streamlit as st

st.set_page_config(page_title="Bedriftdata", page_icon="📊", layout="wide")

with st.sidebar:
    if st.button("🔄 Last data på nytt", help="Tøm mellomlager og les basen på nytt"):
        st.cache_data.clear()
        st.cache_resource.clear()
        st.rerun()

sider = [
    st.Page("sider/oversikt.py", title="Oversikt", icon="🏠", url_path="oversikt", default=True),
    st.Page("sider/enheter.py", title="Enhetsregisteret", icon="🏢", url_path="enheter"),
    st.Page("sider/regnskap.py", title="Regnskap", icon="📈", url_path="regnskap"),
    st.Page("sider/roller.py", title="Roller", icon="👥", url_path="roller"),
    st.Page("sider/aarsregnskap.py", title="Årsregnskap (PDF)", icon="📄", url_path="aarsregnskap"),
    st.Page("sider/valutakurser.py", title="Valutakurser", icon="💱", url_path="valutakurser"),
]
st.navigation(sider).run()
