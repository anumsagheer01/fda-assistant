import time
import requests
from db import engine
from sqlalchemy import text

BACKEND = "http://127.0.0.1:8000"

QUERIES = [
    # IBUPROFEN
    ("ibuprofen", "What are the warnings for ibuprofen?"),
    ("ibuprofen", "Can I take ibuprofen if I have kidney problems?"),
    ("ibuprofen", "What is the dosage for ibuprofen?"),
    ("ibuprofen", "Is ibuprofen safe during pregnancy?"),
    ("ibuprofen", "What are the side effects of ibuprofen?"),
    ("ibuprofen", "Can ibuprofen cause stomach bleeding?"),
    ("ibuprofen", "What drugs interact with ibuprofen?"),
    ("ibuprofen", "Can children take ibuprofen?"),
    ("ibuprofen", "What happens if I overdose on ibuprofen?"),
    ("ibuprofen", "Is ibuprofen safe for elderly patients?"),

    # ACETAMINOPHEN
    ("acetaminophen", "What is the max dose of acetaminophen per day?"),
    ("acetaminophen", "Can I take acetaminophen with alcohol?"),
    ("acetaminophen", "Is acetaminophen safe during pregnancy?"),
    ("acetaminophen", "What are the liver warnings for acetaminophen?"),
    ("acetaminophen", "What are the side effects of acetaminophen?"),
    ("acetaminophen", "Can children take acetaminophen?"),
    ("acetaminophen", "What drugs interact with acetaminophen?"),
    ("acetaminophen", "What are signs of acetaminophen overdose?"),
    ("acetaminophen", "Can I take acetaminophen with ibuprofen?"),
    ("acetaminophen", "Is acetaminophen safe for elderly?"),

    # METFORMIN
    ("metformin", "What are the side effects of metformin?"),
    ("metformin", "Can metformin cause lactic acidosis?"),
    ("metformin", "What is the dosage for metformin?"),
    ("metformin", "Is metformin safe during pregnancy?"),
    ("metformin", "What are the contraindications for metformin?"),
    ("metformin", "Can I drink alcohol while taking metformin?"),
    ("metformin", "What drugs interact with metformin?"),
    ("metformin", "Should metformin be taken with food?"),
    ("metformin", "Can metformin cause kidney problems?"),
    ("metformin", "What are the warnings for metformin?"),

    # ATORVASTATIN
    ("atorvastatin", "Can atorvastatin cause muscle pain?"),
    ("atorvastatin", "What are the side effects of atorvastatin?"),
    ("atorvastatin", "Is atorvastatin safe during pregnancy?"),
    ("atorvastatin", "What drugs interact with atorvastatin?"),
    ("atorvastatin", "Can atorvastatin cause liver damage?"),
    ("atorvastatin", "What is the dosage for atorvastatin?"),
    ("atorvastatin", "Can I eat grapefruit while taking atorvastatin?"),
    ("atorvastatin", "What are the contraindications for atorvastatin?"),
    ("atorvastatin", "Can atorvastatin cause memory problems?"),
    ("atorvastatin", "What are the warnings for atorvastatin?"),

    # AMOXICILLIN
    ("amoxicillin", "What are the side effects of amoxicillin?"),
    ("amoxicillin", "Can I take amoxicillin if I am allergic to penicillin?"),
    ("amoxicillin", "What is the dosage for amoxicillin?"),
    ("amoxicillin", "Is amoxicillin safe during pregnancy?"),
    ("amoxicillin", "What drugs interact with amoxicillin?"),
    ("amoxicillin", "Can amoxicillin cause diarrhea?"),
    ("amoxicillin", "What are the contraindications for amoxicillin?"),
    ("amoxicillin", "Can children take amoxicillin?"),
    ("amoxicillin", "Can amoxicillin cause allergic reactions?"),
    ("amoxicillin", "What are the warnings for amoxicillin?"),

    # LISINOPRIL
    ("lisinopril", "Can lisinopril cause a dry cough?"),
    ("lisinopril", "What are the side effects of lisinopril?"),
    ("lisinopril", "Is lisinopril safe during pregnancy?"),
    ("lisinopril", "What drugs interact with lisinopril?"),
    ("lisinopril", "What is the dosage for lisinopril?"),
    ("lisinopril", "Can lisinopril cause kidney problems?"),
    ("lisinopril", "What are the contraindications for lisinopril?"),
    ("lisinopril", "Can lisinopril raise potassium levels?"),
    ("lisinopril", "What are the warnings for lisinopril?"),
    ("lisinopril", "Can lisinopril cause low blood pressure?"),

    # SERTRALINE
    ("sertraline", "What are the side effects of sertraline?"),
    ("sertraline", "Is sertraline safe during pregnancy?"),
    ("sertraline", "What drugs interact with sertraline?"),
    ("sertraline", "Can sertraline cause suicidal thoughts?"),
    ("sertraline", "What is the dosage for sertraline?"),
    ("sertraline", "Can I drink alcohol while taking sertraline?"),
    ("sertraline", "What are the warnings for sertraline?"),
    ("sertraline", "How long does sertraline take to work?"),
    ("sertraline", "Can sertraline cause weight gain?"),
    ("sertraline", "What are the contraindications for sertraline?"),

    # WARFARIN
    ("warfarin", "What foods interact with warfarin?"),
    ("warfarin", "What are the bleeding risks with warfarin?"),
    ("warfarin", "What drugs interact with warfarin?"),
    ("warfarin", "What is the dosage for warfarin?"),
    ("warfarin", "Is warfarin safe during pregnancy?"),
    ("warfarin", "What are the side effects of warfarin?"),
    ("warfarin", "What are the contraindications for warfarin?"),
    ("warfarin", "Can warfarin cause hair loss?"),
    ("warfarin", "What are the warnings for warfarin?"),
    ("warfarin", "Can elderly patients take warfarin safely?"),

    # ALBUTEROL
    ("albuterol", "What are the side effects of albuterol?"),
    ("albuterol", "How do I use an albuterol inhaler?"),
    ("albuterol", "Is albuterol safe during pregnancy?"),
    ("albuterol", "What drugs interact with albuterol?"),
    ("albuterol", "Can albuterol cause heart palpitations?"),
    ("albuterol", "What are the warnings for albuterol?"),
    ("albuterol", "What is the dosage for albuterol?"),
    ("albuterol", "Can children use albuterol?"),
    ("albuterol", "What are the contraindications for albuterol?"),
    ("albuterol", "Can albuterol cause tremors?"),

    # PREDNISONE
    ("prednisone", "What are the side effects of prednisone?"),
    ("prednisone", "Can prednisone cause weight gain?"),
    ("prednisone", "Is prednisone safe during pregnancy?"),
    ("prednisone", "What drugs interact with prednisone?"),
    ("prednisone", "Can prednisone cause diabetes?"),
    ("prednisone", "What are the warnings for prednisone?"),
    ("prednisone", "What is the dosage for prednisone?"),
    ("prednisone", "Can prednisone weaken the immune system?"),
    ("prednisone", "What are the contraindications for prednisone?"),
    ("prednisone", "Can prednisone cause bone loss?"),
]

GOOD_DISTANCE_THRESHOLD = 0.65
MIN_GOOD_CHUNKS = 2

def evaluate():
    print(f"\nRunning benchmark on {len(QUERIES)} queries...\n")

    results = []
    latencies = []
    fallback_count = 0

    for i, (drug, query) in enumerate(QUERIES):
        start = time.perf_counter()
        try:
            resp = requests.get(
                f"{BACKEND}/rag/search",
                params={"q": query, "k": 5},
                timeout=30
            )
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)

            if resp.status_code != 200:
                results.append(False)
                print(f"  [{i+1:03d}] FAIL (http {resp.status_code}) — {drug}: {query[:50]}")
                continue

            data = resp.json()
            matches = data.get("matches", [])
            used_fallback = data.get("used_fallback", False)
            if used_fallback:
                fallback_count += 1

            good_chunks = [
                m for m in matches
                if m.get("distance") is not None and float(m["distance"]) < GOOD_DISTANCE_THRESHOLD
            ]
            success = len(good_chunks) >= MIN_GOOD_CHUNKS
            results.append(success)

            status = "OK  " if success else "MISS"
            fb = " [fallback]" if used_fallback else ""
            print(f"  [{i+1:03d}] {status}{fb} — {drug}: {query[:55]}")

        except Exception as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            latencies.append(elapsed_ms)
            results.append(False)
            print(f"  [{i+1:03d}] ERROR — {e}")

    # ── RESULTS ──
    total = len(results)
    passed = sum(results)
    coverage = (passed / total) * 100

    avg_latency = sum(latencies) / len(latencies)
    latencies_sorted = sorted(latencies)
    p95_latency = latencies_sorted[int(len(latencies_sorted) * 0.95)]

    print(f"""
{'='*55}
BENCHMARK RESULTS
{'='*55}
Total queries     : {total}
Passed            : {passed}
Failed            : {total - passed}
Coverage          : {coverage:.1f}%
Fallback triggered: {fallback_count} times ({(fallback_count/total)*100:.1f}%)

Latency
  Average         : {avg_latency:.1f}ms
  p95             : {p95_latency:.1f}ms
{'='*55}

  Coverage        : {coverage:.0f}%
  Avg latency     : {avg_latency:.0f}ms
  p95 latency     : {p95_latency:.0f}ms
  Fallback rate   : {(fallback_count/total)*100:.0f}%
  Queries tested  : {total}
{'='*55}
    """)

if __name__ == "__main__":
    evaluate()