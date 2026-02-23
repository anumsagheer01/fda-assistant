import json
import hashlib
from sqlalchemy import create_engine, text
from dotenv import load_dotenv
import os

load_dotenv()

DB_URL = os.getenv("DB_URL", "postgresql+psycopg2://fda:fda_password@localhost:5433/fda_db")
engine = create_engine(DB_URL, future=True)

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
                INSERT INTO label_chunks
                (label_id, section, chunk_index, content, content_hash)
                VALUES (:label_id, :section, :chunk_index, :content, :content_hash)
                ON CONFLICT (label_id, section, chunk_index) DO NOTHING;
            """), {
                "label_id": label_id,
                "section": section,
                "chunk_index": chunk_index,
                "content": content,
                "content_hash": content_hash,
            })
        conn.commit()

def save_embedding(chunk_id, embedding):
    emb_str = "[" + ",".join([str(float(x)) for x in embedding]) + "]"
    with engine.connect() as conn:
        conn.execute(text("""
            UPDATE label_chunks SET embedding = :emb WHERE id = :id;
        """), {"emb": emb_str, "id": chunk_id})
        conn.commit()

def get_chunks_without_embeddings():
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, content FROM label_chunks
            WHERE embedding IS NULL ORDER BY id;
        """)).mappings().all()
    return [dict(r) for r in rows]

def get_recent_labels(limit=10):
    with engine.connect() as conn:
        rows = conn.execute(text("""
            SELECT id, drug_query, brand_name, generic_name, manufacturer, effective_time, fetched_at
            FROM drug_labels ORDER BY id DESC LIMIT :limit;
        """), {"limit": limit}).mappings().all()
    return [dict(r) for r in rows]