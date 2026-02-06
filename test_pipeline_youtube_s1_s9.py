
import logging
import json
import sys
import asyncio
from app.graph.graph import run_stage_sequence

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

def test_pipeline_s1_s9():
    # YouTube URL containing the target claim
    url = "https://www.youtube.com/watch?v=YTv8xPurZfk"
    
    initial_state = {
        "trace_id": "test-youtube-trace-s1-s9",
        "input_type": "url",
        "input_payload": url,
        "language": "ko",
        "search_mode": "exploration"
    }

    print(f"INFO:test_pipeline:Testing Full Pipeline (S1-S9) for URL: {url}")
    print("="*60)
    
    try:
        # Run Stages 1 through 9
        final_state = run_stage_sequence(initial_state, start_stage="stage01_normalize", end_stage="stage09_judge") 
        
        print("\n" + "="*60)
        print(" [VERIFICATION] Stage 1 (Normalize) ")
        print("="*60)
        print(f"Claim: {final_state.get('claim_text')}")
        transcript = final_state.get('transcript', '')
        print(f"Transcript Length: {len(transcript)} chars")

        print("\n" + "="*60)
        print(" [VERIFICATION] Stage 2 (Query Gen) ")
        print("="*60)
        queries = final_state.get('query_variants') or []
        print(f"Query Count: {len(queries)}")
        for q in queries:
            print(f"- [{q.get('type')}] {q.get('text')}")

        print("\n" + "="*60)
        print(" [VERIFICATION] Stage 3 (Collect) ")
        print("="*60)
        candidates = final_state.get('evidence_candidates') or []
        print(f"Candidates Found: {len(candidates)}")

        print("\n" + "="*60)
        print(" [VERIFICATION] Stage 5 (Top-K) ")
        print("="*60)
        citations = final_state.get('citations') or []
        print(f"Selected Citations: {len(citations)}")
        for i, cit in enumerate(citations):
            print(f"{i+1}. [{cit.get('score'):.2f}] {cit.get('title')}")
            print(f"   URL: {cit.get('url')}")

        print("\n" + "="*60)
        print(" [VERIFICATION] Stage 9 (Judge) ")
        print("="*60)
        verdict = final_state.get('final_verdict') or {}
        print(f"Final Judgment: {verdict.get('label')}")
        print(f"Confidence: {verdict.get('confidence_score')}")
        print(f"Summary: {verdict.get('summary')}")

    except Exception as e:
        print(f"\n>>> PIPELINE EXECUTION FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pipeline_s1_s9()
