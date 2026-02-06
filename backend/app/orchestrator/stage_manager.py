"""
Stage Manager (Facade/Registry).

Stage 로직은 그대로 유지하고, orchestrator는 각 Stage의 run()만 호출합니다.
"""

from collections.abc import Awaitable
from typing import Callable
from typing import cast

from app.graph.state import GraphState, RegistryStageName
from app.stages.stage01_normalize.node import run as stage01_normalize
from app.stages.stage02_querygen.node import run as stage02_querygen
from app.stages.stage03_collect.node import run as stage03_collect
from app.stages.stage03_collect.node import run_wiki as stage03_collect_wiki
from app.stages.stage03_collect.node import run_web as stage03_collect_web
from app.stages.stage03_collect.node import run_merge as stage03_collect_merge
from app.stages.stage03_collect.node import run_web_async as stage03_collect_web_async
from app.stages.stage03_collect.node import run_wiki_async as stage03_collect_wiki_async
from app.stages.stage04_score.node import run as stage04_score
from app.stages.stage05_topk.node import run as stage05_topk
from app.stages.stage05_topk.node import run_async as stage05_topk_async
from app.stages.stage06_verify_support.node import run as stage06_verify_support
from app.stages.stage07_verify_skeptic.node import run as stage07_verify_skeptic
from app.stages.stage08_aggregate.node import run as stage08_aggregate
from app.stages.stage09_judge.node import run as stage09_judge


StageFn = Callable[[GraphState], GraphState]
AsyncStageFn = Callable[[GraphState], Awaitable[GraphState]]


STAGE_REGISTRY: dict[RegistryStageName, StageFn] = {
    "stage01_normalize": cast(StageFn, stage01_normalize),
    "stage02_querygen": cast(StageFn, stage02_querygen),
    "stage03_collect": cast(StageFn, stage03_collect),
    "stage03_wiki": cast(StageFn, stage03_collect_wiki),
    "stage03_web": cast(StageFn, stage03_collect_web),
    "stage03_merge": cast(StageFn, stage03_collect_merge),
    "stage04_score": cast(StageFn, stage04_score),
    "stage05_topk": cast(StageFn, stage05_topk),
    "stage06_verify_support": cast(StageFn, stage06_verify_support),
    "stage07_verify_skeptic": cast(StageFn, stage07_verify_skeptic),
    "stage08_aggregate": cast(StageFn, stage08_aggregate),
    "stage09_judge": cast(StageFn, stage09_judge),
}

ASYNC_STAGE_REGISTRY: dict[RegistryStageName, AsyncStageFn] = {
    "stage03_wiki": cast(AsyncStageFn, stage03_collect_wiki_async),
    "stage03_web": cast(AsyncStageFn, stage03_collect_web_async),
    "stage05_topk": cast(AsyncStageFn, stage05_topk_async),
}


def run(stage_name: RegistryStageName, state: GraphState) -> GraphState:
    """Stage run 호출 (로직 변경 없음)."""
    if stage_name not in STAGE_REGISTRY:
        raise ValueError(f"Unknown stage: {stage_name}")
    return STAGE_REGISTRY[stage_name](state)


def get_async(stage_name: RegistryStageName) -> AsyncStageFn | None:
    """Return async-native stage function when available."""
    return ASYNC_STAGE_REGISTRY.get(stage_name)
