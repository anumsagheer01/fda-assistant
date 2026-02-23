import httpx
import time
import asyncio
from db import init_db, save_label, save_chunks, save_embedding, get_chunks_without_embeddings, engine
from sqlalchemy import text
from sentence_transformers import SentenceTransformer

model = SentenceTransformer("all-MiniLM-L6-v2", device="cpu")

DRUGS = [
    "ibuprofen", "acetaminophen", "aspirin", "metformin", "atorvastatin",
    "lisinopril", "amoxicillin", "omeprazole", "metoprolol", "amlodipine",
    "simvastatin", "losartan", "albuterol", "gabapentin", "sertraline",
    "levothyroxine", "fluoxetine", "azithromycin", "hydrochlorothiazide", "furosemide",
    "prednisone", "tramadol", "ciprofloxacin", "clopidogrel", "warfarin",
    "insulin", "montelukast", "cetirizine", "loratadine", "pantoprazole",
    "escitalopram", "bupropion", "duloxetine", "clonazepam", "alprazolam",
    "zolpidem", "cyclobenzaprine", "naproxen", "meloxicam", "doxycycline"
]

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
        chunks.append(text[start:start+size])
        start += size - overlap
    return chunks

async def fetch_label(drug_name):
    url = "https://api.fda.gov/drug/label.json"
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(url, params={"search": f"openfda.generic_name:{drug_name}", "limit": 1})
        if resp.status_code != 200 or not resp.json().get("results"):
            resp = await client.get(url, params={"search": f"openfda.brand_name:{drug_name}", "limit": 1})
        if resp.status_code != 200:
            return None
        results = resp.json().get("results", [])
        if not results:
            return None
        return results[0]

async def process_drug(drug_name):
    print(f"  Fetching {drug_name}...")
    r = await fetch_label(drug_name)
    if not r:
        print(f"  SKIP {drug_name} — not found")
        return False

    openfda = r.get("openfda", {})
    brand_name    = openfda.get("brand_name", [""])[0]
    generic_name  = openfda.get("generic_name", [""])[0]
    manufacturer  = openfda.get("manufacturer_name", [""])[0]
    effective_time = r.get("effective_time", "")

    sections = {}
    for s in SECTIONS:
        val = r.get(s)
        if val:
            sections[s] = val[0] if isinstance(val, list) else val

    if not sections:
        print(f"  SKIP {drug_name} — no sections")
        return False

    label_id = save_label(drug_name, brand_name, generic_name, manufacturer, effective_time, sections, r)

    all_chunks = []
    for section, content in sections.items():
        for i, chunk in enumerate(chunk_text(content)):
            all_chunks.append((section, i, chunk))
    save_chunks(label_id, all_chunks)

    print(f"  OK {drug_name} — {len(sections)} sections, {len(all_chunks)} chunks, label_id={label_id}")
    return True

async def main():
    init_db()
    print(f"\nLoading {len(DRUGS)} drugs...\n")

    for drug in DRUGS:
        await process_drug(drug)
        time.sleep(0.5)  

    print("\nEmbedding all chunks without embeddings...")
    chunks = get_chunks_without_embeddings()
    print(f"Found {len(chunks)} chunks to embed")

    for i, chunk in enumerate(chunks):
        embedding = model.encode(chunk["content"], normalize_embeddings=True)
        save_embedding(chunk["id"], embedding)
        if (i + 1) % 50 == 0:
            print(f"  Embedded {i+1}/{len(chunks)}")

    print(f"\nDone! All {len(chunks)} chunks embedded.")

    with engine.connect() as conn:
        label_count = conn.execute(text("SELECT COUNT(*) FROM drug_labels")).scalar()
        chunk_count = conn.execute(text("SELECT COUNT(*) FROM label_chunks")).scalar()
        embedded_count = conn.execute(text("SELECT COUNT(*) FROM label_chunks WHERE embedding IS NOT NULL")).scalar()
    print(f"\nDatabase summary:")
    print(f"  Labels : {label_count}")
    print(f"  Chunks : {chunk_count}")
    print(f"  Embedded: {embedded_count}")

asyncio.run(main())