import requests
import streamlit as st

st.set_page_config(
    page_title="FDA Evidence Assistant",
    page_icon="💊",
    layout="centered",
    initial_sidebar_state="collapsed",
)

BACKEND_URL = "http://127.0.0.1:8000"

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;1,400&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

.stApp { background: #f8f7f4 !important; }
.block-container { padding-top: 2.5rem !important; padding-bottom: 4rem !important; max-width: 820px !important; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; color: #1a1a2e !important; }
#MainMenu, footer, header { visibility: hidden; }

.stTextInput input {
    background: #ffffff !important; border: 1.5px solid #e2ddd6 !important;
    border-radius: 12px !important; color: #1a1a2e !important;
    font-family: 'Inter', sans-serif !important; font-size: 15px !important;
    padding: 13px 16px !important; box-shadow: 0 1px 3px rgba(0,0,0,0.04) !important;
}
.stTextInput input:focus { border-color: #4a6cf7 !important; box-shadow: 0 0 0 3px rgba(74,108,247,0.08) !important; }
.stTextInput input::placeholder { color: #b0a99f !important; }
.stTextInput label {
    color: #8c8476 !important; font-family: 'JetBrains Mono', monospace !important;
    font-size: 10px !important; letter-spacing: 1.2px !important;
    text-transform: uppercase !important; font-weight: 500 !important;
}
.stSlider label {
    color: #8c8476 !important; font-family: 'JetBrains Mono', monospace !important;
    font-size: 10px !important; letter-spacing: 1.2px !important; text-transform: uppercase !important;
}
div.stButton > button {
    background: #1a1a2e !important; color: #f8f7f4 !important; border: none !important;
    border-radius: 12px !important; padding: 13px 28px !important; font-size: 14px !important;
    font-weight: 500 !important; font-family: 'Inter', sans-serif !important;
    letter-spacing: 0.3px !important; width: 100% !important;
}
div.stButton > button:hover { background: #2d2d4e !important; }
.streamlit-expanderHeader {
    background: #ffffff !important; border: 1.5px solid #e2ddd6 !important;
    border-radius: 10px !important; color: #5a5450 !important;
    font-family: 'JetBrains Mono', monospace !important; font-size: 12px !important;
}
.streamlit-expanderContent {
    background: #fdfcfa !important; border: 1.5px solid #e2ddd6 !important;
    border-top: none !important; color: #5a5450 !important;
    font-size: 13px !important; line-height: 1.75 !important;
}
[data-testid="stDataFrame"] {
    border-radius: 12px !important; overflow: hidden !important;
    border: 1.5px solid #e2ddd6 !important; box-shadow: 0 2px 8px rgba(0,0,0,0.04) !important;
}
.stAlert { border-radius: 12px !important; }
hr { border-color: #e2ddd6 !important; }
</style>
""", unsafe_allow_html=True)


# HEADER
st.markdown("""
<div style="display:flex;align-items:center;justify-content:space-between;
            border-bottom:1.5px solid #e2ddd6;padding-bottom:20px;margin-bottom:40px;">
  <div style="display:flex;align-items:center;gap:10px;">
    <div style="width:32px;height:32px;background:#1a1a2e;border-radius:8px;
                display:flex;align-items:center;justify-content:center;">
      <span style="color:#f8f7f4;font-size:13px;font-weight:600;
                   font-family:'JetBrains Mono',monospace;">Rx</span>
    </div>
    <span style="font-family:'Playfair Display',serif;font-size:20px;color:#1a1a2e;">
      FDA Evidence Assistant
    </span>
  </div>
  <span style="font-family:'JetBrains Mono',monospace;font-size:10px;color:#8c8476;
               background:#f0ede8;border:1px solid #e2ddd6;padding:4px 10px;
               border-radius:20px;letter-spacing:0.8px;">AGENTIC RAG</span>
</div>
""", unsafe_allow_html=True)


# HERO
st.markdown("""
<div style="margin-bottom:40px;">
  <h1 style="font-family:'Playfair Display',serif;font-size:46px;line-height:1.15;
             letter-spacing:-1px;margin-bottom:14px;color:#1a1a2e;font-weight:600;">
    Ask anything about<br>any <em style="color:#4a6cf7;">drug label</em>
  </h1>
  <p style="color:#8c8476;font-size:15px;max-width:480px;line-height:1.75;font-weight:300;">
  </p>
</div>
""", unsafe_allow_html=True)


# METRICS
st.markdown("""
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:36px;">
  <div style="background:#ffffff;border:1.5px solid #e2ddd6;border-radius:14px;
              padding:18px 16px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,0.04);">
    <div style="font-family:'Playfair Display',serif;font-size:26px;color:#4a6cf7;">20,000+</div>
    <div style="font-size:10px;color:#b0a99f;margin-top:4px;
                font-family:'JetBrains Mono',monospace;letter-spacing:0.5px;">FDA DRUGS</div>
  </div>
  <div style="background:#ffffff;border:1.5px solid #e2ddd6;border-radius:14px;
              padding:18px 16px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,0.04);">
    <div style="font-family:'Playfair Display',serif;font-size:26px;color:#2a9d6e;">95%</div>
    <div style="font-size:10px;color:#b0a99f;margin-top:4px;
                font-family:'JetBrains Mono',monospace;letter-spacing:0.5px;">COVERAGE</div>
  </div>
  <div style="background:#ffffff;border:1.5px solid #e2ddd6;border-radius:14px;
              padding:18px 16px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,0.04);">
    <div style="font-family:'Playfair Display',serif;font-size:26px;color:#1a1a2e;">72ms</div>
    <div style="font-size:10px;color:#b0a99f;margin-top:4px;
                font-family:'JetBrains Mono',monospace;letter-spacing:0.5px;">AVG LATENCY</div>
  </div>
  <div style="background:#ffffff;border:1.5px solid #e2ddd6;border-radius:14px;
              padding:18px 16px;text-align:center;box-shadow:0 1px 4px rgba(0,0,0,0.04);">
    <div style="font-family:'Playfair Display',serif;font-size:26px;color:#4a6cf7;">9</div>
    <div style="font-size:10px;color:#b0a99f;margin-top:4px;
                font-family:'JetBrains Mono',monospace;letter-spacing:0.5px;">SECTIONS</div>
  </div>
</div>
""", unsafe_allow_html=True)


def divider(label):
    st.markdown(f"""
    <div style="font-family:'JetBrains Mono',monospace;font-size:10px;color:#b0a99f;
                letter-spacing:1.5px;text-transform:uppercase;margin:36px 0 14px 0;
                display:flex;align-items:center;gap:12px;">
      {label}
      <span style="flex:1;height:1px;background:#e2ddd6;display:inline-block;"></span>
    </div>
    """, unsafe_allow_html=True)


# SEARCH
divider("Search")

col1, col2 = st.columns([1, 2])
with col1:
    drug_name = st.text_input("Drug Name", placeholder="drug name")
with col2:
    question = st.text_input("Your Question", placeholder="user query")

top_k = st.slider("Evidence chunks to retrieve", min_value=1, max_value=10, value=5)

if st.button("Get Answer"):
    if not drug_name.strip():
        st.warning("Please enter a drug name.")
        st.stop()
    if not question.strip():
        st.warning("Please enter a question.")
        st.stop()

    # step 1 — fetch, chunk, embed the drug label
    with st.spinner(f"Fetching FDA label for {drug_name}..."):
        r1 = requests.get(
            f"{BACKEND_URL}/assist/label_summary",
            params={"drug_name": drug_name},
            timeout=60
        )
    if r1.status_code != 200:
        st.error(f"Could not fetch label: {r1.status_code}")
        st.stop()

    label_data = r1.json()
    if "error" in label_data:
        st.error(f"FDA API: {label_data['error']}")
        st.stop()

    # get the label_id that was just fetched
    label_id = label_data.get("label_id")

    # step 2 — generate answer searching ONLY within this drug's label
    with st.spinner("Generating answer from FDA label..."):
        r2 = requests.get(
            f"{BACKEND_URL}/assist/answer",
            params={"q": question, "k": top_k, "label_id": label_id},
            timeout=60
        )
    if r2.status_code != 200:
        st.error(f"Answer failed: {r2.status_code}")
        st.stop()

    data = r2.json()
    answer = data.get("answer", "")
    citations = data.get("citations", [])
    used_fallback = data.get("used_fallback", False)

    fb_label = "keyword fallback" if used_fallback else "semantic search"
    fb_color = "#c97c2a" if used_fallback else "#2a9d6e"

    # ANSWER CARD
    divider("Answer")
    st.markdown(f"""
    <div style="background:#ffffff;border:1.5px solid #e2ddd6;border-radius:16px;
                overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.05);margin-bottom:8px;">
      <div style="padding:14px 22px;border-bottom:1.5px solid #f0ede8;
                  display:flex;align-items:center;justify-content:space-between;
                  background:#fdfcfa;">
        <span style="font-family:'JetBrains Mono',monospace;font-size:12px;
                     color:#4a6cf7;font-weight:500;">
          {label_data.get('brand_name') or drug_name}
        </span>
        <span style="font-family:'JetBrains Mono',monospace;font-size:10px;
                     color:{fb_color};">{fb_label}</span>
      </div>
      <div style="padding:22px;font-size:15px;line-height:1.85;
                  color:#3a3730;font-weight:300;">{answer}</div>
    </div>
    """, unsafe_allow_html=True)

    # EVIDENCE
    if citations:
        divider("FDA Label Evidence")
        for c in citations:
            section   = c.get("section", "unknown")
            dist      = c.get("distance")
            dist_str  = f"{float(dist):.4f}" if dist is not None else "—"
            chunk_id  = c.get("id", "?")
            label_id_c= c.get("label_id", "?")
            chunk_idx = c.get("chunk_index", "?")
            dist_color = (
                "#2a9d6e" if dist and float(dist) < 0.4
                else "#c97c2a" if dist and float(dist) < 0.6
                else "#c0392b"
            )

            st.markdown(f"""
            <div style="background:#ffffff;border:1.5px solid #e2ddd6;border-radius:12px;
                        overflow:hidden;margin-bottom:10px;">
              <div style="background:#fdfcfa;padding:10px 16px;
                          border-bottom:1.5px solid #f0ede8;
                          display:flex;align-items:center;justify-content:space-between;">
                <div style="display:flex;align-items:center;gap:10px;">
                  <span style="font-family:'JetBrains Mono',monospace;font-size:11px;
                               color:#4a6cf7;font-weight:500;">[{chunk_id}]</span>
                  <span style="font-size:10px;font-family:'JetBrains Mono',monospace;
                               background:#eef1fe;border:1px solid #d0d8fc;
                               color:#4a6cf7;padding:2px 8px;border-radius:4px;">{section}</span>
                  <span style="font-size:10px;color:#b0a99f;
                               font-family:'JetBrains Mono',monospace;">
                    label {label_id_c} · chunk {chunk_idx}
                  </span>
                </div>
                <span style="font-family:'JetBrains Mono',monospace;
                             font-size:10px;color:#b0a99f;">
                  dist <span style="color:{dist_color};">{dist_str}</span>
                </span>
              </div>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("View FDA label text"):
                chunk_resp = requests.get(
                    f"{BACKEND_URL}/db/chunk/{chunk_id}", timeout=10
                )
                if chunk_resp.status_code == 200:
                    st.write(chunk_resp.json().get("content", ""))
                else:
                    st.caption("Could not load chunk.")


# SAVED LABELS
divider("Saved Labels")

col1, col2 = st.columns([3, 1])
with col1:
    show_n = st.number_input("Show last N records", min_value=1, max_value=50, value=10)
with col2:
    st.markdown("<div style='margin-top:26px;'>", unsafe_allow_html=True)
    st.button("Refresh", key="refresh")
    st.markdown("</div>", unsafe_allow_html=True)

try:
    r = requests.get(
        f"{BACKEND_URL}/db/recent_labels",
        params={"limit": int(show_n)},
        timeout=10
    )
    if r.status_code == 200:
        items = r.json().get("items", [])
        if not items:
            st.info("No saved labels yet. Search a drug above to save one.")
        else:
            st.dataframe(items, use_container_width=True)
            label_ids = [str(x["id"]) for x in items if "id" in x]
            chosen = st.selectbox("Inspect a saved label", label_ids)
            if chosen:
                det = requests.get(
                    f"{BACKEND_URL}/db/label/{chosen}", timeout=10
                )
                if det.status_code == 200:
                    d = det.json()
                    st.markdown(f"""
                    <div style="background:#ffffff;border:1.5px solid #e2ddd6;
                                border-radius:14px;padding:20px;margin-top:12px;
                                box-shadow:0 1px 4px rgba(0,0,0,0.04);">
                      <div style="font-family:'Playfair Display',serif;font-size:18px;
                                  margin-bottom:14px;color:#1a1a2e;">
                        {d.get('brand_name') or d.get('drug_query','')}
                        <span style="color:#4a6cf7;font-size:14px;margin-left:8px;">
                          #{d['id']}
                        </span>
                      </div>
                      <div style="font-family:'JetBrains Mono',monospace;font-size:11px;
                                  color:#8c8476;line-height:2.2;">
                        Generic &nbsp;: <span style="color:#5a5450;">{d.get('generic_name','—')}</span><br>
                        Brand &nbsp;&nbsp;&nbsp;: <span style="color:#5a5450;">{d.get('brand_name','—')}</span><br>
                        Effective: <span style="color:#5a5450;">{d.get('effective_time','—')}</span>
                      </div>
                    </div>
                    """, unsafe_allow_html=True)
                    with st.expander("View raw label sections"):
                        st.json(d.get("sections", {}))
except Exception as e:
    st.error("Could not reach backend.")
    st.exception(e)


# FOOTER
st.markdown("""
<div style="text-align:center;padding:48px 0 16px 0;
            border-top:1.5px solid #e2ddd6;margin-top:48px;">
  <p style="font-family:'JetBrains Mono',monospace;font-size:10px;
             color:#b0a99f;letter-spacing:0.5px;">
    Data from
    <a href="https://open.fda.gov/" style="color:#4a6cf7;text-decoration:none;">
      openFDA Drug Label API
    </a>
    &nbsp;·&nbsp; For informational use only &nbsp;·&nbsp; Not medical advice
  </p>
</div>
""", unsafe_allow_html=True)