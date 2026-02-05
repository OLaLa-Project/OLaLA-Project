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

    search_queries: List[Dict[str, Any]]

    wiki_candidates: List[Dict[str, Any]]
    web_candidates: List[Dict[str, Any]]
    evidence_candidates: List[Dict[str, Any]]
    scored_evidence: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]
    evidence_topk: List[Dict[str, Any]]
    risk_flags: List[str]
    verdict_support: Dict[str, Any]
    verdict_skeptic: Dict[str, Any]
    # Stage9 판결을 위해 Stage8에서 정제한 입력 패키지
    support_pack: Dict[str, Any]
    skeptic_pack: Dict[str, Any]
    evidence_index: Dict[str, Any]
    judge_prep_meta: Dict[str, Any]
    judge_retrieval: List[Dict[str, Any]]
    final_verdict: Dict[str, Any]
    user_result: Dict[str, Any]
    prompt_normalize_user: str
    prompt_normalize_system: str
    prompt_querygen_user: str
    prompt_querygen_system: str
    slm_raw_normalize: str
    slm_raw_querygen: str
    normalize_claims: list[dict]
    prompt_support_user: str
    prompt_support_system: str
    prompt_skeptic_user: str
    prompt_skeptic_system: str
    prompt_judge_user: str
    prompt_judge_system: str
    slm_raw_support: str
    slm_raw_skeptic: str
    slm_raw_judge: str

    stage_logs: Annotated[List[Dict[str, Any]], operator.add]
    stage_outputs: Annotated[Dict[str, Any], operator.or_]
