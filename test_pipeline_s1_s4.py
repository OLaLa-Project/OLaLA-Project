
import logging
import json
import sys
from app.graph.graph import run_stage_sequence

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

def test_pipeline_s1_s4():
    # YouTube URL containing the target claim
    url = "https://www.youtube.com/watch?v=YTv8xPurZfk"
    
    initial_state = {
        "trace_id": "test-s1-s4-verify",
        "input_type": "url",
        "input_payload": url,
        "language": "ko",
        "search_mode": "exploration"
    }

    print(f"INFO:test_pipeline:Testing Pipeline Stages 1-4 for URL: {url}")
    print("="*60)
    
    try:
        # Run Stages 1 through 4
        final_state = run_stage_sequence(initial_state, start_stage="stage01_normalize", end_stage="stage04_score")
        
        print("\n" + "="*60)
        print(" [VERIFICATION] Stage 1 (Normalize) ")
        print("="*60)
        print(f"Claim: {final_state.get('claim_text')}")
        transcript = final_state.get('transcript', '')
        print(f"Transcript Length: {len(transcript)} chars")
        
        ce = final_state.get('canonical_evidence', {})
        print(f"Canonical Evidence Snippet: {ce.get('snippet', '')[:100]}...")

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
        print(" [VERIFICATION] Stage 4 (Score) ")
        print("="*60)
        scored = final_state.get('scored_evidence') or []
        print(f"Scored Evidence: {len(scored)}")
        if scored:
            print(f"Top 1 Score: {scored[0].get('score')}")
            print(f"Top 1 Title: {scored[0].get('title')}")

    except Exception as e:
        print(f"\n>>> PIPELINE EXECUTION FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pipeline_s1_s4()
