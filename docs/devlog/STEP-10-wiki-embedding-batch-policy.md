# STEP-10 Wiki Embedding Batch Policy

- Date: 2026-02-07
- Status: Completed
- Scope: Phase 2의 `임베딩 배치 정책 수립` 완료

## 목표
wiki DB 임베딩 누락(`embedding IS NULL`)을 운영 가능한 절차로 백필하고, 중단/재개/상태점검/실패복구 기준을 스크립트와 문서로 고정한다.

## 수행 작업
1. 백필 엔진 추가
- 파일: `services/backend/app/tools/wiki_embeddings_backfill.py`
- 핵심:
  - 누락 chunk cursor 스캔
  - 배치 임베딩 + DB 업데이트
  - 배치 실패 시 분할 재시도(문제 chunk 격리)
  - stop-file 기반 안전 중단
  - JSON 진행 로그/실패 로그 출력

2. 운영 스크립트 표준화
- 파일:
  - `scripts/wiki_embeddings_backfill.sh`
  - `scripts/wiki_embeddings_status.sh`
  - `scripts/wiki_embeddings_stop.sh`
  - `scripts/wiki_embeddings_resume.sh`
- 핵심:
  - 백필 실행 전 `backend/wiki-db` 상태 보장
  - 임베딩 커버리지/stop 상태 즉시 확인
  - 안전 중단/재개 지원
  - `ollama` 컨테이너 기동은 opt-in(`OLALA_START_OLLAMA=1` 또는 `--with-ollama`)으로 제한

3. 정책 문서화
- 파일: `docs/WIKI_EMBEDDINGS_POLICY.md`
- 내용:
  - bootstrap/maintenance 배치 기준
  - 실패 복구 가이드
  - 완료 판정(`missing=0`) 및 `WIKI_EMBEDDINGS_READY=true` 전환 절차

4. 진행표/액션 정리 반영
- 파일:
  - `docs/STEP_BY_STEP.md`
  - `docs/NEXT_ACTIONS.md`
  - `docs/devlog/INDEX.md`
- 내용:
  - Phase 2 완료 처리
  - 임베딩 상태/백필 단계를 공식 실행 순서에 편입

## 검증 결과
1. 백필 엔진 실행 검증
- `docker compose -f infra/docker/docker-compose.beta.yml exec -T backend python -m app.tools.wiki_embeddings_backfill --help` 통과
- `docker compose -f infra/docker/docker-compose.beta.yml exec -T backend python -m app.tools.wiki_embeddings_backfill --dry-run --batch-size 64 --max-chunks 128 --report-every 1` 통과

2. 운영 스크립트 검증
- `bash scripts/wiki_embeddings_status.sh` 통과
- `bash scripts/wiki_embeddings_stop.sh` -> stop 파일 생성 확인
- `bash scripts/wiki_embeddings_resume.sh` -> stop 파일 제거 확인
- `bash scripts/wiki_embeddings_backfill.sh --dry-run --batch-size 32 --max-chunks 64 --report-every 1` 통과(ollama 자동기동 비활성 기본값)

3. 상태 기준 확인
- baseline: `embedded=0`, `missing=1002975`, `coverage_pct=0.00`

## 기존 대비 변경 사항
- 기존:
  - `embed_missing`가 요청 단위로 일부만 채우는 형태라 대량 운영 백필 정책 부재
- 변경:
  - 대량/증분 운영을 분리한 배치 정책 + 제어 스크립트 도입
- 효과:
  - 임베딩 단계가 수동 임시작업에서 재현 가능한 운영 절차로 전환

## 남은 리스크
1. 백필 실작업 시간
- 대량 데이터(약 100만 chunk) 특성상 완료까지 장시간 필요

2. Ollama 자원/이미지 리스크
- 내부 ollama 사용 시 첫 이미지 pull 시간이 길 수 있음
- 처리량은 CPU/RAM 자원에 크게 의존

3. 원격 배포 전 최종 확인 필요
- 임베딩 완료 후 `WIKI_EMBEDDINGS_READY=true` 전환 및 스모크 재검증 필요

## 다음 단계
- STEP-11: 원격 배포 제외 기준 최종 프로덕션 하드닝 점검(운영 변수/헬스체크/복구 리허설)
