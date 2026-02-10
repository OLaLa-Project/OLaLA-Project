import operator
from typing import Any, Literal, TypeAlias, TypedDict

from typing_extensions import Annotated, TypeGuard

SearchMode: TypeAlias = Literal["auto", "lexical", "fts", "vector"]
SearchQueryTypeLiteral: TypeAlias = Literal["wiki", "news", "web", "verification", "direct"]

StageName: TypeAlias = Literal[
    "stage01_normalize",
    "stage02_querygen",
    "adapter_queries",
    "stage03_wiki",
    "stage03_web",
    "stage03_merge",
    "stage04_score",
    "stage05_topk",
    "stage06_verify_support",
    "stage07_verify_skeptic",
    "stage08_aggregate",
    "stage09_judge",
]

PublicStageName: TypeAlias = Literal[
    "stage01_normalize",
    "stage02_querygen",
    "adapter_queries",
    "stage03_collect",
    "stage03_wiki",
    "stage03_web",
    "stage03_merge",
    "stage04_score",
    "stage05_topk",
    "stage06_verify_support",
    "stage07_verify_skeptic",
    "stage08_aggregate",
    "stage09_judge",
]

RegistryStageName: TypeAlias = Literal[
    "stage01_normalize",
    "stage02_querygen",
    "stage03_collect",
    "stage03_wiki",
    "stage03_web",
    "stage03_merge",
    "stage04_score",
    "stage05_topk",
    "stage06_verify_support",
    "stage07_verify_skeptic",
    "stage08_aggregate",
    "stage09_judge",
]

STAGE_ORDER: tuple[StageName, ...] = (
    "stage01_normalize",
    "stage02_querygen",
    "adapter_queries",
    "stage03_wiki",
    "stage03_web",
    "stage03_merge",
    "stage04_score",
    "stage05_topk",
    "stage06_verify_support",
    "stage07_verify_skeptic",
    "stage08_aggregate",
    "stage09_judge",
)

_STAGE_SET = frozenset(STAGE_ORDER)
_START_STAGE_ALIASES: dict[str, StageName] = {"stage03_collect": "stage03_wiki"}
_END_STAGE_ALIASES: dict[str, StageName] = {"stage03_collect": "stage03_merge"}


def is_stage_name(value: str) -> TypeGuard[StageName]:
    return value in _STAGE_SET


def normalize_stage_name(value: str | None, *, for_end: bool = False) -> StageName | None:
    if value is None:
        return None
    aliases = _END_STAGE_ALIASES if for_end else _START_STAGE_ALIASES
    candidate = aliases.get(value, value)
    if is_stage_name(candidate):
        return candidate
    return None


class SearchQuery(TypedDict, total=False):
    type: SearchQueryTypeLiteral
    text: str
    search_mode: SearchMode
    meta: dict[str, Any]


class GraphState(TypedDict, total=False):
    trace_id: str
    checkpoint_thread_id: str
    checkpoint_resumed: bool
    checkpoint_expired: bool
    input_type: Literal["url", "text", "image"]
    input_payload: str
    user_request: str
    language: str
    search_mode: str
    normalize_mode: Literal["llm", "basic"]
    include_full_outputs: bool

    claim_text: str
    original_intent: Literal["verification", "exploration"]
    claim_mode: Literal["fact", "rumor", "mixed"]
    verification_priority: Literal["high", "normal"]
    risk_markers: list[str]
    canonical_evidence: dict[str, Any]
    entity_map: dict[str, Any]

    query_variants: list[dict[str, Any]]
    keyword_bundles: dict[str, Any]
    search_constraints: dict[str, Any]
    query_core_fact: str
    querygen_prompt_used: str
    querygen_claims: list[dict[str, Any]]
    search_queries: list[SearchQuery]

    wiki_candidates: list[dict[str, Any]]
    stage03_wiki_diagnostics: dict[str, Any]
    web_candidates: list[dict[str, Any]]
    stage03_web_diagnostics: dict[str, Any]
    stage03_merge_stats: dict[str, Any]
    evidence_candidates: list[dict[str, Any]]
    scored_evidence: list[dict[str, Any]]
    score_diagnostics: dict[str, Any]
    citations: list[dict[str, Any]]
    evidence_topk: list[dict[str, Any]]
    evidence_topk_support: list[dict[str, Any]]
    evidence_topk_skeptic: list[dict[str, Any]]
    risk_flags: list[str]
    topk_diagnostics: dict[str, Any]
    verdict_support: dict[str, Any]
    stage06_diagnostics: dict[str, Any]
    verdict_skeptic: dict[str, Any]
    stage07_diagnostics: dict[str, Any]
    # Stage9 판결을 위해 Stage8에서 정제한 입력 패키지
    support_pack: dict[str, Any]
    skeptic_pack: dict[str, Any]
    evidence_index: dict[str, Any]
    judge_prep_meta: dict[str, Any]
    judge_retrieval: list[dict[str, Any]]
    stage09_diagnostics: dict[str, Any]
    final_verdict: dict[str, Any]
    user_result: dict[str, Any]
    prompt_normalize_user: str
    prompt_normalize_system: str
    prompt_querygen_user: str
    prompt_querygen_system: str
    slm_raw_normalize: str
    slm_raw_querygen: str
    normalize_claims: list[dict[str, Any]]
    prompt_support_user: str
    prompt_support_system: str
    prompt_skeptic_user: str
    prompt_skeptic_system: str
    prompt_judge_user: str
    prompt_judge_system: str
    slm_raw_support: str
    slm_raw_skeptic: str
    slm_raw_judge: str

    stage_logs: Annotated[list[dict[str, Any]], operator.add]
    stage_outputs: Annotated[dict[str, Any], operator.or_]
    stage_full_outputs: Annotated[dict[str, Any], operator.or_]
