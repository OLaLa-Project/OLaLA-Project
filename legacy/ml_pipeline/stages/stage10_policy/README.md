# Stage 10: Policy Guard (정책 필터링)

> **담당**: Common (이은지, 성세빈)

## 역할
최종 판정을 정책에 따라 필터링하고 최종 응답을 생성합니다.

## 입력/출력

| 구분 | 필드 | 설명 |
|------|------|------|
| 입력 | `judgment` | 최종 판정 |
| 입력 | `normalized_claim` | 원본 주장 |
| 출력 | `final_result` | 최종 응답 |

## 정책 필터링

다음 경우 `REFUSED` 처리:
- 정치적 선동
- 혐오 발언
- 개인정보 침해
- 기타 민감 주제

## 최종 응답 형식

```python
{
    "label": "TRUE",  # TRUE/FALSE/MIXED/UNVERIFIED/REFUSED
    "confidence": 0.92,
    "summary": "해당 주장은 사실로 확인됩니다.",
    "evidences": [...]
}
```

## 구현 체크리스트

- [ ] 금지 주제 목록 정의
- [ ] 키워드 필터링
- [ ] 응답 포맷 정리

## 작업 파일

`node.py`의 `policy_node` 함수를 구현하세요.
