# OLaLA ML Pipeline (LangGraph)

LangGraph 기반 10단계 가짜뉴스 검증 파이프라인입니다.

## 파이프라인 흐름

```
[입력] → Stage1 → Stage2 → Stage3 → Stage4 → Stage5
                                                 ↓
[출력] ← Stage10 ← Stage9 ← Stage8 ← Stage6 + Stage7 (병렬)
```

## Stage 담당

| Stage | 이름 | 담당 | 폴더 |
|-------|------|------|------|
| 1 | normalize | Team A | `stages/stage1_normalize/` |
| 2 | querygen | Team A | `stages/stage2_querygen/` |
| 3 | collect | Team A | `stages/stage3_collect/` |
| 4 | score | Team A | `stages/stage4_score/` |
| 5 | topk | Team A | `stages/stage5_topk/` |
| 6 | verify_support | Team B | `stages/stage6_verify_support/` |
| 7 | verify_skeptic | Team B | `stages/stage7_verify_skeptic/` |
| 8 | aggregate | Team B | `stages/stage8_aggregate/` |
| 9 | judge | Common | `stages/stage9_judge/` |
| 10 | policy_guard | Common | `stages/stage10_policy/` |

## 폴더 구조

```
ml_pipeline/
├── README.md           ← 지금 보는 파일
├── graph.py            ← LangGraph 파이프라인 정의
├── requirements.txt
└── stages/
    ├── stage1_normalize/
    │   ├── __init__.py
    │   ├── node.py     ← 메인 로직
    │   └── README.md
    ├── stage2_querygen/
    ├── ...
    └── stage10_policy/
```

## 시작하기

### 1. 의존성 설치
```bash
pip install -r requirements.txt
```

### 2. 파이프라인 실행 (테스트)
```bash
python graph.py
```

## 각 Stage 구현 방법

각 Stage 폴더의 `node.py` 파일에서 함수를 구현하세요:

```python
def my_stage_node(state: dict) -> dict:
    # 입력: 이전 Stage에서 전달받은 state
    # 처리: 해당 Stage 로직
    # 출력: 다음 Stage로 전달할 state
    return updated_state
```
