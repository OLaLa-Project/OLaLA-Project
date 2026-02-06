
import logging
import json
import sys
import asyncio
from app.graph.graph import run_stage_sequence

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

def test_pipeline_full():
    # YouTube URL containing the target claim
    url = "https://www.youtube.com/watch?v=YTv8xPurZfk"
    
    initial_state = {
        "trace_id": "test-youtube-trace-full",
        "input_type": "url",
        "input_payload": url,
        "language": "ko",
        "search_mode": "exploration"
    }

    print(f"INFO:test_pipeline:Testing Full Pipeline for URL: {url}")
    print("="*60)
    
    try:
        # Run Stages 1 through 5 (and beyond if configured)
        # Using the default sequence defined in graph.py which includes up to stage09 usually
        # But we can limit to stage05 if desired. Let's run full to see end-to-end.
        # Run Stages 1 through 5
        final_state = run_stage_sequence(initial_state, start_stage="stage01_normalize", end_stage="stage05_topk") 
        
        print("\n" + "="*60)
        print(" [VERIFICATION] Stage 1 & 2 Summary ")
        print("="*60)
        print(f"Claim: {final_state.get('claim_text')}")
        transcript = final_state.get('transcript', '')
        print(f"Transcript: {len(transcript)} chars")
        print(f"Query Count: {len(final_state.get('query_variants') or [])}")

        print("\n" + "="*60)
        print(" [VERIFICATION] Stage 3 (Collect) ")
        print("="*60)
        candidates = final_state.get('evidence_candidates')
        if candidates:
            print(f"Candidates Found: {len(candidates)}")
            print(f"Sample Candidate: {candidates[0].get('title', 'No Title')}")
        else:
             print("No candidates found.")

        print("\n" + "="*60)
        print(" [VERIFICATION] Stage 4 (Score) ")
        print("="*60)
        scored = final_state.get('scored_evidence')
        if scored:
            print(f"Scored Items: {len(scored)}")
            print(f"Top Score: {scored[0].get('score')}")
        else:
            print("No scored evidence present (Check previous stage).")

        print("\n" + "="*60)
        print(" [VERIFICATION] Stage 5 (Top-K) ")
        print("="*60)
        citations = final_state.get('citations')
        if citations:
            print(f"Selected Citations: {len(citations)}")
            for i, cit in enumerate(citations):
                print(f"{i+1}. [{cit.get('score'):.2f}] {cit.get('title')}")
                print(f"   URL: {cit.get('url')}")
        else:
             print("No citations selected.")

    except Exception as e:
        print(f"\n>>> PIPELINE EXECUTION FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pipeline_full()
