"""
Quick test script for vector-optimized query generation.
Tests Stage 2 output to verify search_mode assignment.
"""
import json
import sys
sys.path.insert(0, '/app')

from app.stages.stage02_querygen.node import postprocess_queries

# Test case 1: Descriptive wiki query (should get vector mode)
test_input_1 = {
    "core_fact": "니파바이러스",
    "query_variants": [
        {"type": "wiki", "text": "니파바이러스의 증상과 전파 경로"},
        {"type": "wiki", "text": "니파바이러스"},
        {"type": "news", "text": "니파바이러스 뉴스"}
    ],
    "keyword_bundles": {"primary": ["니파바이러스"], "secondary": []},
    "search_constraints": {}
}

# Test case 2: Concise wiki query (should get lexical mode)
test_input_2 = {
    "core_fact": "세종대왕",
    "query_variants": [
        {"type": "wiki", "text": "세종대왕"},
        {"type": "news", "text": "세종대왕 기념"}
    ],
    "keyword_bundles": {"primary": ["세종대왕"], "secondary": []},
    "search_constraints": {}
}

# Test case 3: LLM explicitly specifies search_mode
test_input_3 = {
    "core_fact": "코로나19",
    "query_variants": [
        {"type": "wiki", "search_mode": "vector", "text": "코로나19 치료제와 예방법"},
        {"type": "wiki", "search_mode": "lexical", "text": "코로나19"}
    ],
    "keyword_bundles": {"primary": ["코로나19"], "secondary": []},
    "search_constraints": {}
}

print("=" * 60)
print("Test 1: Descriptive wiki query (auto-assign vector)")
print("=" * 60)
result1 = postprocess_queries(test_input_1, "니파바이러스")
print(json.dumps(result1, ensure_ascii=False, indent=2))

print("\n" + "=" * 60)
print("Test 2: Concise wiki query (auto-assign lexical)")
print("=" * 60)
result2 = postprocess_queries(test_input_2, "세종대왕")
print(json.dumps(result2, ensure_ascii=False, indent=2))

print("\n" + "=" * 60)
print("Test 3: LLM-specified search_mode (preserve)")
print("=" * 60)
result3 = postprocess_queries(test_input_3, "코로나19")
print(json.dumps(result3, ensure_ascii=False, indent=2))
