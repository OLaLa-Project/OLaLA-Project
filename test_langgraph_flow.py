
import asyncio
import logging
from app.graph.graph import build_langgraph

# Mock logging
logging.basicConfig(level=logging.INFO)

async def test_graph_flow():
    print("Building LangGraph...")
    app = build_langgraph()
    
    if app is None:
        print("LangGraph not available (import failed?)")
        return

    # Minimal state to trigger the flow
    initial_state = {
        "trace_id": "test-flow",
        "input_type": "url",
        "input_payload": "https://www.youtube.com/watch?v=YTv8xPurZfk",
        "claim_text": "Test Claim",
        "evidence_candidates": [{"title": "Test Evidence", "content": "Test Content", "source_type": "WEB_URL"}],
        "query_variants": []
    }
    
    print("Starting astream...")
    async for output in app.astream(initial_state):
        for node_name, node_state in output.items():
            print(f"Yielded Node: {node_name}")
            if node_name == "stage04_score":
                print(">>> Stage 4 Detected!")
                data = node_state.get("stage_outputs", {}).get(node_name)
                print(f"    Data present? {data is not None}")
                if not data:
                     # Check if it's in the state directly (legacy mode logic in service.py)
                     print(f"    scored_evidence in state? {'scored_evidence' in node_state}")

if __name__ == "__main__":
    asyncio.run(test_graph_flow())
