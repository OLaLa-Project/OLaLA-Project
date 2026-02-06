
import logging
import json
import sys
from app.graph.graph import run_stage_sequence

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

def test_pipeline_stage1_2():
    # YouTube URL containing the target claim
    # Clip: https://www.youtube.com/watch?v=YTv8xPurZfk
    url = "https://www.youtube.com/watch?v=YTv8xPurZfk"
    
    initial_state = {
        "trace_id": "test-youtube-trace-s1-s2",
        "input_type": "url",
        "input_payload": url,
        "language": "ko",
        "search_mode": "exploration"
    }

    print(f"INFO:test_pipeline:Testing Pipeline Stages 1-2 for URL: {url}")
    print("="*60)
    
    try:
        # Run only Stage 1 to Stage 2
        final_state = run_stage_sequence(initial_state, start_stage="stage01_normalize", end_stage="stage02_querygen")
        
        print("\n" + "="*60)
        print(" [VERIFICATION] Stage 1 Output (Claim) ")
        print("="*60)
        print(f"Claim Text: {final_state.get('claim_text')}")
        print(f"Intent    : {final_state.get('original_intent')}")
        # Check transcript presence
        transcript = final_state.get('transcript', '')
        print(f"Transcript stored: {'YES' if transcript else 'NO'} ({len(transcript)} chars)")
        if transcript:
            print(f"Transcript snippet: {transcript[:100]}...")

        print("\n" + "="*60)
        print(" [VERIFICATION] Stage 2 Prompt Used ")
        print("="*60)
        p2_user = final_state.get('prompt_querygen_user', '')
        print(p2_user[:800] + "...")
        if "[YouTube Script]" in p2_user:
             print("\n>>> CONFIRMED: YouTube Dedicated Prompt used.")
        else:
             print("\n>>> NOTICE: YouTube format NOT detected in prompt text (Check if this is intended).")

        print("\n" + "="*60)
        print(" [VERIFICATION] Stage 2 SLM Raw Output ")
        print("="*60)
        print(final_state.get('slm_raw_querygen', 'No output recorded')[:2000])

        print("\n" + "="*60)
        print(" [VERIFICATION] Stage 2 Generated Queries ")
        print("="*60)
        queries = final_state.get('query_variants')
        if queries:
            print(json.dumps(queries, indent=2, ensure_ascii=False))
            print(f"\nTotal Queries: {len(queries)}")
        else:
            print(">>> ERROR: No queries generated (null or empty).")

    except Exception as e:
        print(f"\n>>> PIPELINE EXECUTION FAILED: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    test_pipeline_stage1_2()
