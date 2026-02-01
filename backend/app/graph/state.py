from typing import Any, Dict, List, TypedDict
from typing_extensions import Annotated
import operator


class GraphState(TypedDict, total=False):
    trace_id: str
    input_type: str
    input_payload: str
    user_request: str
    language: str
    search_mode: str

    claim_text: str
    canonical_evidence: Dict[str, Any]
    entity_map: Dict[str, Any]

    query_variants: List[Dict[str, Any]]
    keyword_bundles: Dict[str, Any]
    search_constraints: Dict[str, Any]

    search_queries: List[str]

    evidence_candidates: List[Dict[str, Any]]
    scored_evidence: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]
    evidence_topk: List[Dict[str, Any]]
    risk_flags: List[str]
    verdict_support: Dict[str, Any]
    verdict_skeptic: Dict[str, Any]
    draft_verdict: Dict[str, Any]
    quality_score: int
    final_verdict: Dict[str, Any]
    user_result: Dict[str, Any]

    stage_logs: Annotated[List[Dict[str, Any]], operator.add]
    stage_outputs: Annotated[Dict[str, Any], operator.or_]
