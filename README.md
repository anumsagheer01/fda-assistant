# FDA Evidence Assistant
### Agentic RAG Pipeline for FDA Drug Label Q&A

> Type any drug name, ask a question in plain English, get a cited answer straight from the official FDA label and not random internet sources.


## Why I Built This

Drug information online felt like a mix of websites with half-explanations. I wanted something that answers real questions about warnings, dosage, side effects, and interactions, and also shows exactly where the answer came from. Every response traces back to the official FDA label so you can verify it yourself.

All screenshots included.


## Performance

| Metric | Result |
|---|---|
| Label section types | 9 |
| Retrieval coverage | **95%** |
| Benchmark queries | 100 |
| Average retrieval latency | **72ms** |
| p95 retrieval latency | 88ms |


## How It Works

```
User types drug name and a question
              │
              ▼
        Streamlit UI
              │
              ▼
       FastAPI Backend
              │
    ┌─────────┴──────────┐
    │                    │
    ▼                    ▼
① FETCH             ② REWRITE QUERY
openFDA API         Gemini rewrites plain
Gets official       English into clinical
drug label          FDA terminology
Stores in           for better retrieval
PostgreSQL
    │                    │
    ▼                    ▼
③ CHUNK             ④ RETRIEVE
Split into          Semantic search using
900-char pieces     cosine distance on
with 120-char       384-d embeddings
overlap             (pgvector)
                         │
                         └── If weak results
                             then keyword fallback
                             (ts_vector)
                                  │
                                  ▼
                         ⑤ GENERATE
                         Gemini 2.5 answers
                         using ONLY retrieved
                         FDA evidence
                         Cites exact sections
                              │
                              ▼
                    Answer and Citations in UI
```


## Label Sections Indexed

For each drug, the assistant stores and searches across 9 official FDA label sections:

| Section | What It Covers |
|---|---|
| `adverse_reactions` | Known side effects reported in trials |
| `boxed_warning` | FDA's most serious warnings (black box) |
| `contraindications` | Who should NOT take this drug |
| `dosage_and_administration` | How much and how to take it |
| `drug_interactions` | What it reacts with |
| `precautions` | Cautions for specific situations |
| `use_in_specific_populations` | Pregnancy, children, elderly |
| `warnings` | General safety warnings |
| `warnings_and_cautions` | Extended warning details |


## Tech Stack

| Layer | Technology |
|---|---|
| Backend API | FastAPI, Uvicorn |
| Frontend UI | Streamlit |
| Database | PostgreSQL, pgvector (Dockerized) |
| ORM | SQLAlchemy |
| Embeddings | Hugging Face SentenceTransformers (all-MiniLM-L6-v2, 384-d) |
| LLM | Google Gemini 2.5 Flash |
| Data Source | openFDA Drug Label API |
| Containerization | Docker and docker-compose |


## Run It Locally

```bash
# 1. Clone the repo
git clone https://github.com/anumsagheer01/fda-assistant
cd fda-assistant

# 2. Start the database
docker-compose up -d

# 3. Add your API key
cd backend
cp .env.example .env
# Add your GOOGLE_API_KEY to .env

# 4. Install dependencies
pip install -r requirements.txt

# 5. Start the backend
uvicorn main:app --reload --port 8000

# 6. Start the UI (new terminal)
cd ../ui
streamlit run app.py

# Open http://localhost:8501
```

## Project Structure

```
fda-assistant/
├── backend/
│   ├── main.py              # FastAPI endpoints
│   ├── db.py                # PostgreSQL schema and storage
│   ├── bulk_load.py         # Bulk load drugs initially for testing
│   └── eval.py              # 100-query benchmark
├── ui/
│   └── app.py               # Streamlit frontend
├── docker-compose.yml        # PostgreSQL and pgvector
└── .env.example
```


## Key API Endpoints

| Endpoint | What It Does |
|---|---|
| `GET /assist/label_summary` | Fetch, chunk, and embed a drug label |
| `GET /assist/answer` | Rewrite query, retrieve, generate cited answer |
| `GET /rag/search` | Raw retrieval with two-pass fallback |
| `GET /db/recent_labels` | Browse saved label history |
| `GET /db/chunk/{id}` | Fetch raw chunk text |
| `GET /health` | Health check |


## Why Not Just Google It?

Googling a drug question gives you WebMD summaries, Reddit threads, and 
pharmacy blogs and none of which show you their source or tell you which 
part of the official label they pulled from.

This assistant only answers from the FDA-approved label for that exact drug. 
Every sentence in the answer is traceable to a specific section of the 
official prescribing information, you can expand the evidence chunks and 
read the exact text it used.

That means:
- No opinion, no paraphrasing from unknown sources
- No cross-contamination from other drugs
- Every claim is cited with the section it came from

## Data Sources

- openFDA: https://open.fda.gov/
- openFDA Drug Label API: https://open.fda.gov/apis/drug/label/


**Important:**

-  This tool helps you understand what the FDA label actually says, it does not replace a doctor or pharmacist. 
- FDA labels are written for medical professionals and can be dense. This assistant translates that 
language into plain English so you know what questions to ask your doctor, not so you can skip the appointment. 
- Always verify medical decisions with a qualified healthcare professional.

