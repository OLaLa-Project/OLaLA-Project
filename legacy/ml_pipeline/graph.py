"""
OLaLA ML Pipeline - LangGraph 정의
담당: Common (이은지, 성세빈)
"""

from typing import TypedDict
from langgraph.graph import StateGraph, END

# Stage imports
from stages.stage1_normalize import normalize_node
from stages.stage2_querygen import querygen_node
from stages.stage3_collect import collect_node
from stages.stage4_score import score_node
from stages.stage5_topk import topk_node
from stages.stage6_verify_support import verify_support_node
from stages.stage7_verify_skeptic import verify_skeptic_node
from stages.stage8_aggregate import aggregate_node
from stages.stage9_judge import judge_node
from stages.stage10_policy import policy_node


class PipelineState(TypedDict, total=False):
    """파이프라인 전체 상태"""
    # 기본 정보
    request_id: str
    raw_claim: str

    # Stage 1 출력
    normalized_claim: str
    language: str

    # Stage 2 출력
    queries: list

    # Stage 3 출력
    evidences: list

    # Stage 4 출력
    scored_evidences: list

    # Stage 5 출력
    top_evidences: list

    # Stage 6-7 출력 (병렬)
    support_result: dict
    skeptic_result: dict

    # Stage 8 출력
    aggregated_result: dict

    # Stage 9 출력
    judgment: dict

    # Stage 10 출력 (최종)
    final_result: dict


def build_graph() -> StateGraph:
    """LangGraph 파이프라인 빌드"""
    graph = StateGraph(PipelineState)

    # 노드 추가
    graph.add_node("normalize", normalize_node)
    graph.add_node("querygen", querygen_node)
    graph.add_node("collect", collect_node)
    graph.add_node("score", score_node)
    graph.add_node("topk", topk_node)
    graph.add_node("verify_support", verify_support_node)
    graph.add_node("verify_skeptic", verify_skeptic_node)
    graph.add_node("aggregate", aggregate_node)
    graph.add_node("judge", judge_node)
    graph.add_node("policy_guard", policy_node)

    # 엣지 연결 (순차)
    graph.set_entry_point("normalize")
    graph.add_edge("normalize", "querygen")
    graph.add_edge("querygen", "collect")
    graph.add_edge("collect", "score")
    graph.add_edge("score", "topk")

    # 병렬 처리 (Stage 6, 7)
    graph.add_edge("topk", "verify_support")
    graph.add_edge("topk", "verify_skeptic")

    # 병렬 결과 합류
    graph.add_edge("verify_support", "aggregate")
    graph.add_edge("verify_skeptic", "aggregate")

    # 최종 판정
    graph.add_edge("aggregate", "judge")
    graph.add_edge("judge", "policy_guard")
    graph.add_edge("policy_guard", END)

    return graph.compile()


# 파이프라인 인스턴스
pipeline = build_graph()


async def run_pipeline(request_id: str, claim: str) -> dict:
    """파이프라인 실행"""
    initial_state = {
        "request_id": request_id,
        "raw_claim": claim,
    }

    result = await pipeline.ainvoke(initial_state)
    return result.get("final_result", {})


if __name__ == "__main__":
    # 테스트 실행
    import asyncio

    async def test():
        result = await run_pipeline(
            request_id="test-001",
            claim="대한민국의 수도는 서울이다."
        )
        print(result)

    asyncio.run(test())
