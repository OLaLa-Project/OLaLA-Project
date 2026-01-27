# Team A Guide (Evidence Pipeline)

## Members
- 이윤호
- 성세빈
- 이은지
## Scope
Stage 1~5

## Responsibility
입력 정리 → 쿼리 생성 → 수집/패킹 → 관련도 스코어링 → Top-K 선별

## Working Paths
- `backend/app/stages/stage01_normalize`
- `backend/app/stages/stage02_querygen`
- `backend/app/stages/stage03_retrieve`
- `backend/app/stages/stage04_rerank`
- `backend/app/stages/stage05_topk`
