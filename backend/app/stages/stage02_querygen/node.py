"""
Stage 2 - Query Generation (LLM-Enhanced)

?뺢퇋?붾맂 二쇱옣?쇰줈遺???ㅺ컖??寃??荑쇰━瑜??앹꽦?⑸땲??
LLM ?ㅽ뙣 ??洹쒖튃 湲곕컲(rule-based) fallback???곸슜?⑸땲??

Input state keys:
    - trace_id: str
    - claim_text: str (Stage 1?먯꽌 ?뺢퇋?붾맂 二쇱옣)
    - language: "ko" | "en"
    - canonical_evidence: dict (Stage 1 硫뷀??곗씠??
    - entity_map: dict (Stage 1 ?뷀떚??

Output state keys:
    - query_variants: list[dict] (type, text)
    - keyword_bundles: dict (primary, secondary)
    - search_constraints: dict
"""

import json
import logging
from pathlib import Path
from functools import lru_cache
from typing import Dict, Any, List

from app.stages._shared.slm_client import call_slm1, SLMError
from app.stages._shared.guardrails import parse_json_safe

logger = logging.getLogger(__name__)

# ?꾨＼?꾪듃 ?뚯씪 寃쎈줈
PROMPT_FILE = Path(__file__).parent / "prompt_querygen.txt"

# ?ㅼ젙
MAX_CONTENT_LENGTH = 1500
DEFAULT_LANGUAGE = "ko"


@lru_cache(maxsize=1)
def load_system_prompt() -> str:
    """?쒖뒪???꾨＼?꾪듃 濡쒕뱶 (罹먯떛)."""
    return PROMPT_FILE.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# LLM 湲곕컲 荑쇰━ ?앹꽦
# ---------------------------------------------------------------------------

def generate_queries_with_llm(
    claim: str,
    context: Dict[str, Any],
) -> Dict[str, Any]:
    """
    SLM???ъ슜??寃利앹슜 荑쇰━瑜??앹꽦?⑸땲??

    Returns:
        core_fact, query_variants, keyword_bundles, search_constraints瑜??ы븿?섎뒗 dict.

    Raises:
        SLMError, ValueError: LLM ?몄텧 ?먮뒗 ?뚯떛 ?ㅽ뙣 ??
    """
    system_prompt = load_system_prompt()

    fetched_content = context.get("fetched_content", "")
    has_article = bool(fetched_content)

    if has_article:
        truncated = fetched_content[:MAX_CONTENT_LENGTH]
        context_str = json.dumps(
            {k: v for k, v in context.items() if k != "fetched_content"},
            ensure_ascii=False,
        )
        user_prompt = f"""Input User Text: "{claim}"
[泥⑤???湲곗궗 ?댁슜 ?쒖옉]
{truncated}
[泥⑤???湲곗궗 ?댁슜 ??

Context Hints: {context_str}

???뺣낫瑜?諛뷀깢?쇰줈 JSON ?щ㎎??異쒕젰???앹꽦?섏꽭?? 湲곗궗 ?댁슜???덈떎硫?湲곗궗???듭떖 二쇱옣??理쒖슦?좎쑝濡?諛섏쁺?섏꽭?? `text` ?꾨뱶???덈? 鍮꾩썙?먮㈃ ???⑸땲??"""
    else:
        context_str = json.dumps(context, ensure_ascii=False, default=str)
        user_prompt = f"""Input Text: "{claim}"
Context Hints: {context_str}

???뺣낫瑜?諛뷀깢?쇰줈 JSON ?щ㎎??異쒕젰???앹꽦?섏꽭?? `text` ?꾨뱶???덈? 鍮꾩썙?먮㈃ ???⑸땲??"""

    response = call_slm1(system_prompt, user_prompt)
    parsed = parse_json_safe(response)

    if parsed is None:
        # 1???ъ떆??
        logger.info("JSON ?뚯떛 ?ㅽ뙣, ?ъ떆??)
        retry_prompt = (
            "?댁쟾 ?묐떟???좏슚??JSON???꾨떃?덈떎. "
            "諛섎뱶???좏슚??JSON留?異쒕젰?섏꽭?? ?ㅻⅨ ?ㅻ챸 ?놁씠 JSON留?異쒕젰?섏꽭??"
        )
        response = call_slm1(retry_prompt, user_prompt)
        parsed = parse_json_safe(response)

    if parsed is None:
        raise ValueError(f"JSON ?뚯떛 理쒖쥌 ?ㅽ뙣: {response[:200]}")

    return parsed


def _render_prompt_template(template: str, state: Dict[str, Any]) -> str:
    evidence = state.get("canonical_evidence", {}) or {}
    user_request = state.get("user_request", "")
    title = evidence.get("article_title", "") or ""
    article_text = evidence.get("fetched_content", "") or evidence.get("snippet", "") or ""
    rendered = template
    rendered = rendered.replace("{{user_request}}", user_request)
    rendered = rendered.replace("{{title}}", title)
    rendered = rendered.replace("{{article_text}}", article_text)
    return rendered


def generate_queries_with_prompt_override(
    state: Dict[str, Any],
    template: str,
) -> Dict[str, Any]:
    prompt = _render_prompt_template(template, state)
    response = call_slm1("", prompt)
    parsed = parse_json_safe(response)
    if parsed is None:
        retry_prompt = (
            "?댁쟾 ?묐떟???좏슚??JSON???꾨떃?덈떎. 諛섎뱶???좏슚??JSON留?異쒕젰?섏꽭?? "
            "?ㅻⅨ ?ㅻ챸 ?놁씠 JSON留?異쒕젰?섏꽭??"
        )
        response = call_slm1(retry_prompt, prompt)
        parsed = parse_json_safe(response)
    if parsed is None:
        raise ValueError(f"JSON ?뚯떛 理쒖쥌 ?ㅽ뙣: {response[:200]}")
    parsed["_prompt_used"] = prompt
    return parsed


def _query_variants_from_team_a(parsed: Dict[str, Any]) -> List[Dict[str, Any]]:
    claims = parsed.get("claims") or parsed.get("二쇱옣??) or []
    variants: List[Dict[str, Any]] = []
    for claim in claims:
        query_pack = claim.get("query_pack") or {}
        wiki_db = query_pack.get("wiki_db") if isinstance(query_pack, dict) else None
        news_search = query_pack.get("news_search") if isinstance(query_pack, dict) else None
        if isinstance(wiki_db, dict):
            wiki_db = [wiki_db]
        if isinstance(news_search, str):
            news_search = [news_search]
        for item in wiki_db or []:
            if isinstance(item, dict):
                q = str(item.get("q") or "").strip()
            else:
                q = str(item or "").strip()
            if q:
                variants.append({"type": "wiki", "text": q})
        for q in news_search or []:
            q = str(q).strip()
            if q:
                variants.append({"type": "news", "text": q})
    return variants


def postprocess_queries(
    parsed: Dict[str, Any],
    claim: str,
) -> Dict[str, Any]:
    """
    LLM 異쒕젰 ?꾩쿂由? 鍮?text ?꾨뱶 蹂댁셿, 湲곕낯 援ъ“ 蹂댁옣.
    """
    core_fact = parsed.get("core_fact") or claim

    # query_variants 蹂댁셿
    variants = parsed.get("query_variants", [])
    for q in variants:
        if not q.get("text"):
            qtype = q.get("type", "direct")
            if qtype == "verification":
                q["text"] = f"{core_fact} ?⑺듃泥댄겕"
            elif qtype == "news":
                q["text"] = f"{core_fact} ?댁뒪"
            elif qtype == "contradictory":
                q["text"] = f"{core_fact} 諛섎컯"
            else:
                q["text"] = core_fact

    # 理쒖냼 1媛?荑쇰━ 蹂댁옣
    if not variants:
        variants = [{"type": "direct", "text": core_fact}]

    return {
        "query_variants": variants,
        "keyword_bundles": parsed.get("keyword_bundles", {"primary": [], "secondary": []}),
        "search_constraints": parsed.get("search_constraints", {}),
    }


# ---------------------------------------------------------------------------
# Rule-based fallback
# ---------------------------------------------------------------------------

def generate_rule_based_fallback(claim: str) -> Dict[str, Any]:
    """LLM ?ㅽ뙣 ??洹쒖튃 湲곕컲 荑쇰━ ?앹꽦."""
    words = claim.split()
    keywords = [w for w in words if len(w) > 1]

    variants = [
        {"type": "direct", "text": claim},
        {"type": "verification", "text": f"{claim} ?⑺듃泥댄겕"},
        {"type": "news", "text": f"{claim} ?댁뒪"},
    ]

    return {
        "query_variants": variants,
        "keyword_bundles": {
            "primary": keywords[:3],
            "secondary": keywords[3:6],
        },
        "search_constraints": {"note": "rule-based fallback"},
    }


# ---------------------------------------------------------------------------
# 硫붿씤 ?ㅽ뻾
# ---------------------------------------------------------------------------

def run(state: dict) -> dict:
    """
    Stage 2 ?ㅽ뻾: 寃??荑쇰━ ?앹꽦.

    Stage 1??異쒕젰(claim_text, canonical_evidence, entity_map)??湲곕컲?쇰줈
    ?ㅺ컖??寃??荑쇰━瑜??앹꽦?⑸땲??
    """
    trace_id = state.get("trace_id", "unknown")
    claim_text = state.get("claim_text", "")
    context = state.get("canonical_evidence", {})

    logger.info(f"[{trace_id}] Stage2 ?쒖옉: claim={claim_text[:50]}...")

    if not claim_text:
        logger.warning(f"[{trace_id}] claim_text 鍮꾩뼱?덉쓬, fallback ?곸슜")
        result = generate_rule_based_fallback("")
        state["query_variants"] = result["query_variants"]
        state["keyword_bundles"] = result["keyword_bundles"]
        state["search_constraints"] = result["search_constraints"]
        return state

    try:
        # LLM 湲곕컲 荑쇰━ ?앹꽦 (override prompt 吏??
        prompt_override = state.get("querygen_prompt") or ""
        if prompt_override.strip():
            parsed = generate_queries_with_prompt_override(state, prompt_override)
            variants = _query_variants_from_team_a(parsed)
            if variants:
                result = {
                    "query_variants": variants,
                    "keyword_bundles": parsed.get("keyword_bundles", {"primary": [], "secondary": []}),
                    "search_constraints": parsed.get("search_constraints", {}),
                }
                state["querygen_claims"] = parsed.get("claims") or parsed.get("二쇱옣??) or []
                state["querygen_prompt_used"] = parsed.get("_prompt_used")
            else:
                result = postprocess_queries(parsed, claim_text)
        else:
            parsed = generate_queries_with_llm(claim_text, context)
            result = postprocess_queries(parsed, claim_text)

        logger.info(
            f"[{trace_id}] Stage2 LLM ?꾨즺: "
            f"{len(result['query_variants'])} queries generated"
        )

    except (SLMError, ValueError) as e:
        logger.warning(f"[{trace_id}] LLM 荑쇰━ ?앹꽦 ?ㅽ뙣, fallback ?곸슜: {e}")
        result = generate_rule_based_fallback(claim_text)

    except Exception as e:
        logger.exception(f"[{trace_id}] Stage2 ?덉긽移?紐삵븳 ?ㅻ쪟: {e}")
        result = generate_rule_based_fallback(claim_text)

    # State ?낅뜲?댄듃
    state["query_variants"] = result["query_variants"]
    state["keyword_bundles"] = result["keyword_bundles"]
    state["search_constraints"] = result["search_constraints"]

    if result.get("query_variants"):
        logger.info(f"[{trace_id}] Stage2 ?꾨즺: top_query={result['query_variants'][0]['text']}")
    else:
        logger.info(f"[{trace_id}] Stage2 ?꾨즺: no queries generated")

    return state

