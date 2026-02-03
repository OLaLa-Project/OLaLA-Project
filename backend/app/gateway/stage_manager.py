"""
Stage Manager (Facade/Registry).

Stage 로직은 그대로 유지하고, Gateway는 각 Stage의 run()만 호출합니다.
"""

from typing import Dict, Any, Callable

from app.stages.stage01_normalize.node import run as stage01_normalize
from app.stages.stage02_querygen.node import run as stage02_querygen
from app.stages.stage03_collect.node import run as stage03_collect
from app.stages.stage03_collect.node import run_wiki as stage03_collect_wiki
from app.stages.stage03_collect.node import run_web as stage03_collect_web
from app.stages.stage03_collect.node import run_merge as stage03_collect_merge
from app.stages.stage04_score.node import run as stage04_score
from app.stages.stage05_topk.node import run as stage05_topk
from app.stages.stage06_verify_support.node import run as stage06_verify_support
from app.stages.stage07_verify_skeptic.node import run as stage07_verify_skeptic
from app.stages.stage08_aggregate.node import run as stage08_aggregate
from app.stages.stage09_judge.node import run as stage09_judge


StageFn = Callable[[Dict[str, Any]], Dict[str, Any]]


STAGE_REGISTRY: Dict[str, StageFn] = {
    "stage01_normalize": stage01_normalize,
    "stage02_querygen": stage02_querygen,
    "stage03_collect": stage03_collect,
    "stage03_wiki": stage03_collect_wiki,
    "stage03_web": stage03_collect_web,
    "stage03_merge": stage03_collect_merge,
    "stage04_score": stage04_score,
    "stage05_topk": stage05_topk,
    "stage06_verify_support": stage06_verify_support,
    "stage07_verify_skeptic": stage07_verify_skeptic,
    "stage08_aggregate": stage08_aggregate,
    "stage09_judge": stage09_judge,
}


def run(stage_name: str, state: Dict[str, Any]) -> Dict[str, Any]:
    """Stage run 호출 (로직 변경 없음)."""
    if stage_name not in STAGE_REGISTRY:
        raise ValueError(f"Unknown stage: {stage_name}")
    return STAGE_REGISTRY[stage_name](state)
