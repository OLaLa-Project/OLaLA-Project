# Stage 8: Aggregate (결과 통합)

> **담당**: Team B (김현섭, 윤수민)

## 역할
Stage 6(지지)과 Stage 7(회의)의 결과를 통합합니다.

## 입력/출력

| 구분 | 필드 | 설명 |
|------|------|------|
| 입력 | `support_result` | 지지 검증 결과 |
| 입력 | `skeptic_result` | 회의 검증 결과 |
| 출력 | `aggregated_result` | 통합 결과 |

## 통합 로직

| 지지 | 회의 | 결과 |
|------|------|------|
| support | refute | MIXED (충돌) |
| support | neutral | TRUE 경향 |
| neutral | refute | FALSE 경향 |
| support | support | TRUE (강함) |
| refute | refute | FALSE (강함) |

## 구현 체크리스트

- [ ] 충돌 감지 로직
- [ ] 신뢰도 가중 평균
- [ ] MIXED 케이스 처리

## 작업 파일

`node.py`의 `aggregate_node` 함수를 구현하세요.
