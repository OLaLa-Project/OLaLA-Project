# Stage 7: Verify Skeptic (회의 관점 검증)

> **담당**: Team B (김현섭, 윤수민)

## 역할
증거를 바탕으로 주장을 **회의적 관점**에서 검증합니다.

**Stage 6과 병렬로 실행됩니다.**

## 입력/출력

| 구분 | 필드 | 설명 |
|------|------|------|
| 입력 | `top_evidences` | 상위 증거 리스트 |
| 입력 | `normalized_claim` | 원본 주장 |
| 출력 | `skeptic_result` | 회의 검증 결과 |

## 출력 형식

```python
{
    "stance": "refute",  # support / refute / neutral
    "confidence": 0.75,
    "reasoning": "반박 근거..."
}
```

## 구현 체크리스트

- [ ] SLM2 프롬프트 작성
- [ ] 반박 근거 추출
- [ ] 신뢰도 계산

## 작업 파일

`node.py`의 `verify_skeptic_node` 함수를 구현하세요.
