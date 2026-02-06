
import logging
import json
import sys
from app.graph.graph import run_stage_sequence

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

def test_pipeline_s1_s3():
    # YouTube URL containing the target claim
    url = "https://www.youtube.com/watch?v=YTv8xPurZfk"
    
    initial_state = {
        "trace_id": "test-s1-s3-verify",
        "input_type": "url",
        "input_payload": url,
        "language": "ko",
        "search_mode": "exploration"
    }

    print(f"INFO:test_pipeline:Testing Pipeline Stages 1-3 for URL: {url}")
    print("="*60)
    
    try:
        # Run Stages 1 through 3 (Merge)
        final_state = run_stage_sequence(initial_state, start_stage="stage01_normalize", end_stage="stage03_merge")
        
        print("\n" + "="*60)
        print(" [VERIFICATION] Stage 1 (Normalize) ")
        print("="*60)
        print(f"Claim: {final_state.get('claim_text')}")
        transcript = final_state.get('transcript', '')
        print(f"Transcript Length: {len(transcript)} chars")
        if transcript:
            print(f"Transcript Snippet: {transcript[:100]}...")

        print("\n" + "="*60)
        print(" [VERIFICATION] Stage 2 (Query Gen) ")
        print("="*60)
        queries = final_state.get('query_variants') or []
        print(f"Generated Queries ({len(queries)}):")
        for i, q in enumerate(queries):
            print(f"{i+1}. [{q.get('type')}] {q.get('text')}")

        print("\n" + "="*60)
        print(" [VERIFICATION] Stage 3 (Collect) ")
        print("="*60)
        candidates = final_state.get('evidence_candidates') or []
        print(f"Candidates Found: {len(candidates)}")
        
        # Breakdown by source
        wiki_count = sum(1 for c in candidates if c.get('source_type') == 'WIKIPEDIA')
        web_count = sum(1 for c in candidates if c.get('source_type') == 'WEB_URL')
        print(f" - Wikipedia: {wiki_count}")
        print(f" - Web Search: {web_count}")
        
        if candidates:
            print(f"\nSample Evidence 1: {candidates[0].get('title')}")
            print(f"URL: {candidates[0].get('url')}")

    except Exception as e:
        print(f"\n>>> PIPELINE EXECUTION FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pipeline_s1_s3()
