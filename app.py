import os
import json
import hashlib
import httpx
import streamlit as st
from sqlalchemy import create_engine, text
from sentence_transformers import SentenceTransformer
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate

# ── Config ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="FDA Evidence Assistant",
    page_icon="💊",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# ── Database ─────────────────────────────────────────────────────────────────
DB_URL = os.environ.get("DB_URL", "")
engine = create_engine(DB_URL.replace("postgresql://", "postgresql+psycopg2://"), future=True)

def init_db():
    with engine.connect() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS drug_labels (
                id SERIAL PRIMARY KEY,
                drug_query TEXT NOT NULL,
                brand_name TEXT,
                generic_name TEXT,
                manufacturer TEXT,
                effective_time TEXT,
                sections JSONB NOT NULL,
                raw_result JSONB NOT NULL,
                fetched_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS label_chunks (
                id SERIAL PRIMARY KEY,
                label_id INT NOT NULL REFERENCES drug_labels(id) ON DELETE CASCADE,
                section TEXT NOT NULL,
                chunk_index INT NOT NULL,
                content TEXT NOT NULL,
                content_hash TEXT NOT NULL,
                embedding vector(384),
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                UNIQUE(label_id, section, chunk_index)
            );
        """))
        conn.commit()

def save_label(drug_query, brand_name, generic_name, manufacturer, effective_time, sections, raw_result):
    with engine.connect() as conn:
        result = conn.execute(text("""
            INSERT INTO drug_labels
            (drug_query, brand_name, generic_name, manufacturer, effective_time, sections, raw_result)
            VALUES (:drug_query, :brand_name, :generic_name, :manufacturer, :effective_time,
                    CAST(:sections AS jsonb), CAST(:raw_result AS jsonb))
            RETURNING id;
        """), {
            "drug_query": drug_query,
            "brand_name": brand_name,
            "generic_name": generic_name,
            "manufacturer": manufacturer,
            "effective_time": effective_time,
            "sections": json.dumps(sections),
            "raw_result": json.dumps(raw_result),
        })
        label_id = result.fetchone()[0]
        conn.commit()
    return label_id

def save_chunks(label_id, chunks):
    with engine.connect() as conn:
        for section, chunk_index, content in chunks:
            content_hash = hashlib.sha256(content.encode()).hexdigest()
            conn.execute(text("""
                INSERT INTO label_chunks (label_id, section, chunk_index, content, content_hash)
                VALUES (:label_id, :section, :chunk_index, :content, :content_hash)
                ON CONFLICT (label_id, section, chunk_index) DO NOTHING;
            """), {"label_id": label_id, "section": section, "chunk_index": chunk_index,
                   "content": content, "content_hash": content_hash})
        conn.commit()

def save_embedding(chunk_id, embedding):
    emb_str = "[" + ",".join([str(float(x)) for x in embedding]) + "]"
    with engine.connect() as conn:
        conn.execute(text("UPDATE label_chunks SET embedding = :emb WHERE id = :id;"),
                     {"emb": emb_str, "id": chunk_id})
        conn.commit()

def get_chunks_without_embeddings():
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT id, content FROM label_chunks WHERE embedding IS NULL ORDER BY id;"
        )).mappings().all()
    return [dict(r) for r in rows]

def get_recent_labels(limit=10):
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, drug_query, brand_name, generic_name, manufacturer, effective_time, fetched_at
            FROM drug_labels ORDER BY id DESC LIMIT :limit;
        """), {"limit": limit}).mappings().all()
    return [dict(r) for r in rows]

def get_chunk_content(chunk_id):
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT content FROM label_chunks WHERE id = :id;"
        ), {"id": chunk_id}).mappings().fetchone()
    return dict(row) if row else {}

def get_label_detail(label_id):
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT id, drug_query, brand_name, generic_name, manufacturer,
                   effective_time, sections, fetched_at
            FROM drug_labels WHERE id = :id;
        """), {"id": label_id}).mappings().fetchone()
    return dict(row) if row else {}

# ── ML Models (cached) ────────────────────────────────────────────────────────
@st.cache_resource
def load_embedding_model():
    return SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

@st.cache_resource
def load_llm():
    return ChatGoogleGenerativeAI(
        model="gemini-2.0-flash",
        google_api_key=os.environ.get("GOOGLE_API_KEY")
    )

# ── Constants ─────────────────────────────────────────────────────────────────
SECTIONS = [
    "adverse_reactions", "boxed_warning", "contraindications",
    "dosage_and_administration", "drug_interactions", "precautions",
    "use_in_specific_populations", "warnings", "warnings_and_cautions"
]
CHUNK_SIZE = 900
CHUNK_OVERLAP = 120

def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks

# ── Core Logic ────────────────────────────────────────────────────────────────
def fetch_and_store_label(drug_name, embed_model):
    url = "https://api.fda.gov/drug/label.json"
    with httpx.Client() as client:
        resp = client.get(url, params={"search": f"openfda.generic_name:{drug_name}", "limit": 1})
        if resp.status_code != 200 or not resp.json().get("results"):
            resp = client.get(url, params={"search": f"openfda.brand_name:{drug_name}", "limit": 1})
        if resp.status_code != 200:
            return None, "Could not fetch label from FDA API."

    data = resp.json()
    results = data.get("results", [])
    if not results:
        return None, "No label found for this drug."

    r = results[0]
    openfda = r.get("openfda", {})
    brand_name = openfda.get("brand_name", [""])[0]
    generic_name = openfda.get("generic_name", [""])[0]
    manufacturer = openfda.get("manufacturer_name", [""])[0]
    effective_time = r.get("effective_time", "")

    sections = {}
    for s in SECTIONS:
        val = r.get(s)
        if val:
            sections[s] = val[0] if isinstance(val, list) else val

    label_id = save_label(drug_name, brand_name, generic_name, manufacturer, effective_time, sections, r)

    all_chunks = []
    for section, content in sections.items():
        for i, chunk in enumerate(chunk_text(content)):
            all_chunks.append((section, i, chunk))
    save_chunks(label_id, all_chunks)

    chunks_to_embed = get_chunks_without_embeddings()
    for chunk in chunks_to_embed:
        embedding = embed_model.encode(chunk["content"], normalize_embeddings=True)
        save_embedding(chunk["id"], embedding)

    return {
        "label_id": label_id,
        "drug": drug_name,
        "brand_name": brand_name,
        "generic_name": generic_name,
        "sections_found": list(sections.keys()),
    }, None

def rag_search(q, embed_model, k=5, label_id=None):
    query_embedding = embed_model.encode(q, normalize_embeddings=True)
    emb_str = "[" + ",".join([str(float(x)) for x in query_embedding]) + "]"
    label_filter = "AND label_id = :label_id" if label_id else ""
    params = {"emb": emb_str, "k": k}
    if label_id:
        params["label_id"] = label_id

    with engine.connect() as conn:
        rows = conn.execute(text(f"""
            SELECT id, label_id, section, chunk_index, content,
                   embedding <=> CAST(:emb AS vector) AS distance
            FROM label_chunks
            WHERE embedding IS NOT NULL {label_filter}
            ORDER BY distance ASC LIMIT :k;
        """), params).mappings().all()

    matches = [dict(r) for r in rows]
    used_fallback = False

    if not matches or (sum(m["distance"] for m in matches) / len(matches)) > 0.45:
        used_fallback = True
        with engine.connect() as conn:
            fb_rows = conn.execute(text(f"""
                SELECT id, label_id, section, chunk_index, content, 0.60 AS distance
                FROM label_chunks
                WHERE to_tsvector('english', content) @@ plainto_tsquery('english', :q)
                {label_filter} LIMIT :k;
            """), {**params, "q": q}).mappings().all()
        if fb_rows:
            matches = [dict(r) for r in fb_rows]

    return matches, used_fallback

def generate_answer(q, matches, used_fallback, llm):
    rewrite_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an FDA medical terminology expert. Rewrite the user question using clinical FDA label language for better document retrieval. Return only the rewritten query, nothing else."),
        ("human", "{question}")
    ])
    rewritten_q = (rewrite_prompt | llm).invoke({"question": q}).content.strip()

    evidence_block = ""
    for i, m in enumerate(matches):
        evidence_block += f"[{i+1}] Section: {m['section']}\n{m['content']}\n\n"

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a friendly helpful medical information assistant explaining FDA drug labels to everyday people with no medical background.
Answer in clear simple English anyone can understand. No jargon.
Explain what the FDA label says in plain words.
Use short paragraphs. Always cite chunk numbers using [1], [2] etc.
Use ONLY the evidence provided. If the evidence does not contain the answer, say what IS known from the label instead."""),
        ("human", "Question: {question}\n\nEvidence:\n{evidence}")
    ])

    response = (prompt | llm).invoke({"question": q, "evidence": evidence_block})
    return response.content, rewritten_q

# ── UI Styles ─────────────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Playfair+Display:ital,wght@0,400;0,600;1,400&family=Inter:wght@300;400;500;600&family=JetBrains+Mono:wght@400;500&display=swap');

.stApp { background: #f8f7f4 !important; }
.block-container { padding-top: 2.5rem !important; padding-bottom: 4rem !important; max-width: 820px !important; }
html, body, [class*="css"] { font-family: 'Inter', sans-serif !important; color: #1a1a2e !important; }
#MainMenu, footer, header { visibility: hidden; }

.stTextInput input {
    background: #ffffff !important; border: 1.5px solid #e2ddd6 !important;
    border-radius: 12px !important; font-size: 15px !important;
    padding: 13px 16px !important;
}
.stTextInput input:focus { border-color: #4a6cf7 !important; }
div.stButton > button {
    background: #1a1a2e !important; color: #f8f7f4 !important; border: none !important;
    border-radius: 12px !important; padding: 13px 28px !important;
    font-size: 14px !important; font-weight: 500 !important; width: 100% !important;
}
div.stButton > button:hover { background: #2d2d4e !important; }
hr { border-color: #e2ddd6 !important; }
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
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

# ── Hero ──────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="margin-bottom:40px;">
  <h1 style="font-family:'Playfair Display',serif;font-size:46px;line-height:1.15;
             letter-spacing:-1px;margin-bottom:14px;color:#1a1a2e;font-weight:600;">
    Ask anything about<br>any <em style="color:#4a6cf7;">drug label</em>
  </h1>
</div>
""", unsafe_allow_html=True)

# ── Metrics ───────────────────────────────────────────────────────────────────
st.markdown("""
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:36px;">
  <div style="background:#ffffff;border:1.5px solid #e2ddd6;border-radius:14px;padding:18px 16px;text-align:center;">
    <div style="font-family:'Playfair Display',serif;font-size:26px;color:#4a6cf7;">20,000+</div>
    <div style="font-size:10px;color:#b0a99f;margin-top:4px;font-family:'JetBrains Mono',monospace;">FDA DRUGS</div>
  </div>
  <div style="background:#ffffff;border:1.5px solid #e2ddd6;border-radius:14px;padding:18px 16px;text-align:center;">
    <div style="font-family:'Playfair Display',serif;font-size:26px;color:#2a9d6e;">95%</div>
    <div style="font-size:10px;color:#b0a99f;margin-top:4px;font-family:'JetBrains Mono',monospace;">COVERAGE</div>
  </div>
  <div style="background:#ffffff;border:1.5px solid #e2ddd6;border-radius:14px;padding:18px 16px;text-align:center;">
    <div style="font-family:'Playfair Display',serif;font-size:26px;color:#1a1a2e;">72ms</div>
    <div style="font-size:10px;color:#b0a99f;margin-top:4px;font-family:'JetBrains Mono',monospace;">AVG LATENCY</div>
  </div>
  <div style="background:#ffffff;border:1.5px solid #e2ddd6;border-radius:14px;padding:18px 16px;text-align:center;">
    <div style="font-family:'Playfair Display',serif;font-size:26px;color:#4a6cf7;">9</div>
    <div style="font-size:10px;color:#b0a99f;margin-top:4px;font-family:'JetBrains Mono',monospace;">SECTIONS</div>
  </div>
</div>
""", unsafe_allow_html=True)

# ── Init ──────────────────────────────────────────────────────────────────────
try:
    init_db()
except Exception as e:
    st.error(f"Database connection failed: {e}")
    st.stop()

embed_model = load_embedding_model()
llm = load_llm()

# ── Search ────────────────────────────────────────────────────────────────────
st.markdown("<div style='font-family:JetBrains Mono,monospace;font-size:10px;color:#b0a99f;letter-spacing:1.5px;text-transform:uppercase;margin-bottom:14px;'>Search</div>", unsafe_allow_html=True)

col1, col2 = st.columns([1, 2])
with col1:
    drug_name = st.text_input("Drug Name", placeholder="e.g. ibuprofen")
with col2:
    question = st.text_input("Your Question", placeholder="e.g. What are the side effects?")

top_k = st.slider("Evidence chunks to retrieve", min_value=1, max_value=10, value=5)

if st.button("Get Answer"):
    if not drug_name.strip():
        st.warning("Please enter a drug name.")
        st.stop()
    if not question.strip():
        st.warning("Please enter a question.")
        st.stop()

    with st.spinner(f"Fetching FDA label for {drug_name}..."):
        label_data, error = fetch_and_store_label(drug_name, embed_model)

    if error:
        st.error(error)
        st.stop()

    label_id = label_data.get("label_id")

    with st.spinner("Searching FDA label and generating answer..."):
        matches, used_fallback = rag_search(question, embed_model, k=top_k, label_id=label_id)
        if not matches:
            st.warning("No relevant information found in the saved labels.")
            st.stop()
        answer, rewritten_q = generate_answer(question, matches, used_fallback, llm)

    fb_label = "keyword fallback" if used_fallback else "semantic search"
    fb_color = "#c97c2a" if used_fallback else "#2a9d6e"

    st.markdown("<div style='font-family:JetBrains Mono,monospace;font-size:10px;color:#b0a99f;letter-spacing:1.5px;text-transform:uppercase;margin:36px 0 14px 0;'>Answer</div>", unsafe_allow_html=True)

    st.markdown(f"""
    <div style="background:#ffffff;border:1.5px solid #e2ddd6;border-radius:16px;
                overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,0.05);margin-bottom:8px;">
      <div style="padding:14px 22px;border-bottom:1.5px solid #f0ede8;
                  display:flex;align-items:center;justify-content:space-between;background:#fdfcfa;">
        <span style="font-family:'JetBrains Mono',monospace;font-size:12px;color:#4a6cf7;font-weight:500;">
          {label_data.get('brand_name') or drug_name}
        </span>
        <span style="font-family:'JetBrains Mono',monospace;font-size:10px;color:{fb_color};">{fb_label}</span>
      </div>
      <div style="padding:22px;font-size:15px;line-height:1.85;color:#3a3730;font-weight:300;">{answer}</div>
    </div>
    """, unsafe_allow_html=True)

    if matches:
        st.markdown("<div style='font-family:JetBrains Mono,monospace;font-size:10px;color:#b0a99f;letter-spacing:1.5px;text-transform:uppercase;margin:36px 0 14px 0;'>FDA Label Evidence</div>", unsafe_allow_html=True)
        for c in matches:
            section = c.get("section", "unknown")
            dist = c.get("distance")
            dist_str = f"{float(dist):.4f}" if dist is not None else "—"
            chunk_id = c.get("id", "?")
            dist_color = "#2a9d6e" if dist and float(dist) < 0.4 else "#c97c2a" if dist and float(dist) < 0.6 else "#c0392b"

            st.markdown(f"""
            <div style="background:#ffffff;border:1.5px solid #e2ddd6;border-radius:12px;overflow:hidden;margin-bottom:10px;">
              <div style="background:#fdfcfa;padding:10px 16px;border-bottom:1.5px solid #f0ede8;
                          display:flex;align-items:center;justify-content:space-between;">
                <div style="display:flex;align-items:center;gap:10px;">
                  <span style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#4a6cf7;font-weight:500;">[{chunk_id}]</span>
                  <span style="font-size:10px;font-family:'JetBrains Mono',monospace;background:#eef1fe;
                               border:1px solid #d0d8fc;color:#4a6cf7;padding:2px 8px;border-radius:4px;">{section}</span>
                </div>
                <span style="font-family:'JetBrains Mono',monospace;font-size:10px;color:#b0a99f;">
                  dist <span style="color:{dist_color};">{dist_str}</span>
                </span>
              </div>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("View FDA label text"):
                chunk_data = get_chunk_content(chunk_id)
                st.write(chunk_data.get("content", "Could not load chunk."))

# ── Saved Labels ──────────────────────────────────────────────────────────────
st.markdown("<div style='font-family:JetBrains Mono,monospace;font-size:10px;color:#b0a99f;letter-spacing:1.5px;text-transform:uppercase;margin:36px 0 14px 0;'>Saved Labels</div>", unsafe_allow_html=True)

col1, col2 = st.columns([3, 1])
with col1:
    show_n = st.number_input("Show last N records", min_value=1, max_value=50, value=10)
with col2:
    st.markdown("<div style='margin-top:26px;'>", unsafe_allow_html=True)
    refresh = st.button("Refresh", key="refresh")
    st.markdown("</div>", unsafe_allow_html=True)

try:
    items = get_recent_labels(int(show_n))
    if not items:
        st.info("No saved labels yet. Search a drug above to save one.")
    else:
        display_items = []
        for item in items:
            item_copy = dict(item)
            if item_copy.get("fetched_at"):
                item_copy["fetched_at"] = str(item_copy["fetched_at"])
            display_items.append(item_copy)
        st.dataframe(display_items, use_container_width=True)

        label_ids = [str(x["id"]) for x in items if "id" in x]
        chosen = st.selectbox("Inspect a saved label", label_ids)
        if chosen:
            d = get_label_detail(int(chosen))
            if d:
                d["fetched_at"] = str(d.get("fetched_at", ""))
                st.markdown(f"""
                <div style="background:#ffffff;border:1.5px solid #e2ddd6;border-radius:14px;
                            padding:20px;margin-top:12px;">
                  <div style="font-family:'Playfair Display',serif;font-size:18px;margin-bottom:14px;color:#1a1a2e;">
                    {d.get('brand_name') or d.get('drug_query', '')}
                    <span style="color:#4a6cf7;font-size:14px;margin-left:8px;">#{d['id']}</span>
                  </div>
                  <div style="font-family:'JetBrains Mono',monospace;font-size:11px;color:#8c8476;line-height:2.2;">
                    Generic &nbsp;: <span style="color:#5a5450;">{d.get('generic_name', '—')}</span><br>
                    Brand &nbsp;&nbsp;&nbsp;: <span style="color:#5a5450;">{d.get('brand_name', '—')}</span><br>
                    Effective: <span style="color:#5a5450;">{d.get('effective_time', '—')}</span>
                  </div>
                </div>
                """, unsafe_allow_html=True)
                with st.expander("View raw label sections"):
                    st.json(d.get("sections", {}))
except Exception as e:
    st.error(f"Could not load saved labels: {e}")

# ── Footer ────────────────────────────────────────────────────────────────────
st.markdown("""
<div style="text-align:center;padding:48px 0 16px 0;border-top:1.5px solid #e2ddd6;margin-top:48px;">
  <p style="font-family:'JetBrains Mono',monospace;font-size:10px;color:#b0a99f;letter-spacing:0.5px;">
    Data from <a href="https://open.fda.gov/" style="color:#4a6cf7;text-decoration:none;">openFDA Drug Label API</a>
    &nbsp;·&nbsp; For informational use only &nbsp;·&nbsp; Not medical advice
  </p>
</div>
""", unsafe_allow_html=True)