import os
import json
import httpx
from fastapi import FastAPI
from dotenv import load_dotenv
from sqlalchemy import text
from sentence_transformers import SentenceTransformer
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_core.prompts import ChatPromptTemplate
from db import init_db, save_label, save_chunks, save_embedding, get_chunks_without_embeddings, get_recent_labels, engine

load_dotenv()

app = FastAPI()
model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")
llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=os.getenv("GOOGLE_API_KEY"))

SECTIONS = [
    "adverse_reactions", "boxed_warning", "contraindications",
    "dosage_and_administration", "drug_interactions", "precautions",
    "use_in_specific_populations", "warnings", "warnings_and_cautions"
]

CHUNK_SIZE = 900
CHUNK_OVERLAP = 120

@app.on_event("startup")
def startup():
    init_db()

def chunk_text(text, size=CHUNK_SIZE, overlap=CHUNK_OVERLAP):
    chunks = []
    start = 0
    while start < len(text):
        end = start + size
        chunks.append(text[start:end])
        start += size - overlap
    return chunks

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/assist/label_summary")

async def label_summary(drug_name: str):
    url = "https://api.fda.gov/drug/label.json"
    async with httpx.AsyncClient() as client:
        resp = await client.get(url, params={"search": f"openfda.generic_name:{drug_name}", "limit": 1})
        if resp.status_code != 200 or not resp.json().get("results"):
            resp = await client.get(url, params={"search": f"openfda.brand_name:{drug_name}", "limit": 1})
        if resp.status_code != 200:
            return {"error": "Could not fetch label"}

    data = resp.json()
    results = data.get("results", [])
    if not results:
        return {"error": "No label found for this drug"}

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

    # chunk
    all_chunks = []
    for section, content in sections.items():
        for i, chunk in enumerate(chunk_text(content)):
            all_chunks.append((section, i, chunk))
    save_chunks(label_id, all_chunks)

    # embed
    chunks_to_embed = get_chunks_without_embeddings()
    for chunk in chunks_to_embed:
        embedding = model.encode(chunk["content"], normalize_embeddings=True)
        save_embedding(chunk["id"], embedding)

    return {
        "label_id": label_id,
        "drug": drug_name,
        "brand_name": brand_name,
        "generic_name": generic_name,
        "sections_found": list(sections.keys()),
    }

@app.get("/rag/search")
def rag_search(q: str, k: int = 5, label_id: int = None):
    query_embedding = model.encode(q, normalize_embeddings=True)
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
            ORDER BY distance ASC
            LIMIT :k;
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
                {label_filter}
                LIMIT :k;
            """), {**params, "q": q}).mappings().all()
        if fb_rows:
            matches = [dict(r) for r in fb_rows]

    return {"matches": matches, "used_fallback": used_fallback}


@app.get("/assist/answer")
def assist_answer(q: str, k: int = 5, label_id: int = None):
    # rewrite query to match FDA clinical language
    rewrite_prompt = ChatPromptTemplate.from_messages([
        ("system", "You are an FDA medical terminology expert. Rewrite the user's question using clinical FDA label language for better document retrieval. Return only the rewritten query, nothing else."),
        ("human", "{question}")
    ])
    rewrite_chain = rewrite_prompt | llm
    rewritten_q = rewrite_chain.invoke({"question": q}).content.strip()

    # search using rewritten query
    search = rag_search(rewritten_q, k, label_id=label_id)
    matches = search["matches"]
    used_fallback = search["used_fallback"]

    if not matches:
        return {"answer": "No relevant information found in the saved labels.", "citations": [], "used_fallback": used_fallback}

    evidence_block = ""
    for i, m in enumerate(matches):
        evidence_block += f"[{i+1}] Section: {m['section']}\n{m['content']}\n\n"

    prompt = ChatPromptTemplate.from_messages([
        ("system", """You are a friendly, helpful medical information assistant explaining FDA drug labels to everyday people with no medical background.

Your job is to answer the user's question in clear, simple English that anyone can understand — no jargon.
- Explain what the FDA label says in plain words
- If something is a risk, explain WHY it is a risk in simple terms
- If the answer is "consult a doctor", explain what specifically to ask the doctor about
- Use short paragraphs, not bullet points
- Always cite which chunk number(s) your answer comes from using [1], [2] etc.
- Use ONLY the evidence provided. Do not use outside knowledge.
- If the evidence does not contain the answer, say what IS known from the label instead of just saying not found.
"""),
        ("human", "Question: {question}\n\nEvidence:\n{evidence}")
    ])

    chain = prompt | llm
    response = chain.invoke({"question": q, "evidence": evidence_block})
    answer = response.content

    citations = []
    for i, m in enumerate(matches):
        citations.append({
            "id": m["id"],
            "label_id": m["label_id"],
            "section": m["section"],
            "chunk_index": m["chunk_index"],
            "distance": float(m["distance"]),
        })

    return {"answer": answer, "citations": citations, "used_fallback": used_fallback}
@app.get("/db/recent_labels")
def recent_labels(limit: int = 10):
    items = get_recent_labels(limit)
    for item in items:
        if item.get("fetched_at"):
            item["fetched_at"] = str(item["fetched_at"])
    return {"items": items}

@app.get("/db/label/{label_id}")
def get_label(label_id: int):
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT id, drug_query, brand_name, generic_name, manufacturer,
                   effective_time, sections, fetched_at
            FROM drug_labels WHERE id = :id;
        """), {"id": label_id}).mappings().fetchone()
    if not row:
        return {"error": "Not found"}
    d = dict(row)
    d["fetched_at"] = str(d["fetched_at"])
    return d

@app.get("/db/chunk/{chunk_id}")
def get_chunk(chunk_id: int):
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT id, label_id, section, chunk_index, content
            FROM label_chunks WHERE id = :id;
        """), {"id": chunk_id}).mappings().fetchone()
    if not row:
        return {"error": "Not found"}
    return dict(row)

if __name__ == "__main__":
    import uvicorn, os
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))