
import asyncio
import logging
import os
import sys
from pprint import pprint

# Add backend to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

# [Hotfix] Override DATABASE_URL for local testing (docker service 'db' -> localhost)
# This must happen before importing app modules that initialize DB engine
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

current_db_url = os.getenv("DATABASE_URL", "")
if "@db:5432" in current_db_url:
    os.environ["DATABASE_URL"] = current_db_url.replace("@db:5432", "@localhost:5432")
    print(f"[*] Patched DATABASE_URL for local host: {os.environ['DATABASE_URL']}")

current_slm_url = os.getenv("SLM_BASE_URL", "")
if "host.docker.internal" in current_slm_url:
    os.environ["SLM_BASE_URL"] = current_slm_url.replace("host.docker.internal", "localhost")
    print(f"[*] Patched SLM_BASE_URL for local host: {os.environ['SLM_BASE_URL']}")

# Import Stages
from app.stages.stage01_normalize import node as s1
from app.stages.stage02_querygen import node as s2
from app.stages.stage03_collect import node as s3
from app.stages.stage04_score import node as s4
from app.stages.stage05_topk import node as s5
from app.stages.stage06_verify_support import node as s6
from app.stages.stage07_verify_skeptic import node as s7
from app.stages.stage08_aggregate import node as s8
from app.stages.stage09_judge import node as s9

# Setup Logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("PipelineTest")

def run_pipeline():
    logger.info(">>> Starting Pipeline Integration Test (S1 -> S8)")

    # 0. Initial State
    state = {
        "trace_id": "test-run-001",
        "claim_text": "딥러닝의 아버지 제프리 힌튼은 노벨 물리학상을 수상했다.", # Fact: 2024 Physics Nobel Prize (True)
        # "claim_text": "지구는 평평하다.", # False Claim
        "language": "ko",
        "search_mode": "auto" # Test our new feature
    }
    
    # 1. Stage 1: Normalize
    logger.info("--- Stage 1: Normalize ---")
    state = s1.run(state)
    logger.info(f"S1 Output: {state.get('claim_text')}")

    # 2. Stage 2: QueryGen
    logger.info("\n--- Stage 2: QueryGen ---")
    state = s2.run(state)
    logger.info(f"S2 Output Queries: {[q['text'] for q in state.get('query_variants', [])]}")

    # 3. Stage 3: Collect
    logger.info("\n--- Stage 3: Collect ---")
    state = s3.run(state)
    candidates = state.get("evidence_candidates", [])
    logger.info(f"S3 Output: {len(candidates)} candidates found.")
    
    # 4. Stage 4: Score
    logger.info("\n--- Stage 4: Score ---")
    state = s4.run(state)
    scored = state.get("scored_evidence", [])
    if scored:
        top_score = max(s['score'] for s in scored)
        logger.info(f"S4 Output: Max Score = {top_score}")

    # 5. Stage 5: TopK
    logger.info("\n--- Stage 5: TopK ---")
    state = s5.run(state)
    topk = state.get("evidence_topk", [])
    logger.info(f"S5 Output: {len(topk)} selected evidence.")
    for idx, item in enumerate(topk):
        print(f"  [{idx+1}] {item['title']} (Score: {item['score']}) [{item['source_type']}]")

    if not topk:
        logger.error("No evidence passed. Pipeline might stop here in real flow.")
        # But we verify S6/S7 handle empty evidence gracefully

    # 6. Stage 6: Verify Support
    logger.info("\n--- Stage 6: Verify Support ---")
    state = s6.run(state)
    v_sup = state.get("verdict_support", {})
    logger.info(f"S6 Output: Stance={v_sup.get('stance')}, Conf={v_sup.get('confidence')}")
    # pprint(v_sup.get('reasoning_bullets'))

    # 7. Stage 7: Verify Skeptic
    logger.info("\n--- Stage 7: Verify Skeptic ---")
    state = s7.run(state)
    v_skep = state.get("verdict_skeptic", {})
    logger.info(f"S7 Output: Stance={v_skep.get('stance')}, Conf={v_skep.get('confidence')}")

    # 8. Stage 8: Aggregate
    logger.info("\n--- Stage 8: Aggregate ---")
    state = s8.run(state)
    draft = state.get("draft_verdict", {})
    quality = state.get("quality_score")
    logger.info(f"S8 Output: Draft Stance={draft.get('stance')}, Quality={quality}")

    # 9. Stage 9: Judge
    logger.info("\n--- Stage 9: Judge ---")
    state = s9.run(state)
    final = state.get("final_verdict", {})

    print("\n" + "="*50)
    print("FINAL VERDICT REPORT (Stage 9)")
    print("="*50)
    print(f"Review Claim: {state.get('claim_text')}")
    print(f"Final Stance: {final.get('stance')}")
    print(f"Confidence: {final.get('confidence')}")
    print(f"Summary: {final.get('summary')}")
    print("-" * 20)
    print("Reasoning:")
    for b in final.get("reasoning_bullets", []):
        print(f" - {b}")
    print("="*50)

if __name__ == "__main__":
    run_pipeline()
