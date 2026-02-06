# Stage 6: Verify Support (지지 관점 검증)

> **담당**: Team B (김현섭, 윤수민)

## 역할
증거를 바탕으로 주장을 **지지하는 관점**에서 검증합니다.

**Stage 7과 병렬로 실행됩니다.**

## 입력/출력

| 구분 | 필드 | 설명 |
|------|------|------|
| 입력 | `top_evidences` | 상위 증거 리스트 |
| 입력 | `normalized_claim` | 원본 주장 |
| 출력 | `support_result` | 지지 검증 결과 |

## 출력 형식

```python
{
    "stance": "support",  # support / refute / neutral
    "confidence": 0.85,
    "reasoning": "판단 근거..."
}
```

## 구현 체크리스트

- [ ] SLM2 프롬프트 작성
- [ ] 지지 근거 추출
- [ ] 신뢰도 계산

## 작업 파일

`node.py`의 `verify_support_node` 함수를 구현하세요.
