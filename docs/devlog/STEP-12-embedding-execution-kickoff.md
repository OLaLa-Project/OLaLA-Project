# STEP-12 Embedding Execution Kickoff

- Date: 2026-02-07
- Status: In Progress
- Scope: wiki 임베딩 실백필 시작 및 장시간 실행 경로 고정

## 목표
wiki chunk 임베딩 생성을 실제로 시작하고, 세션 종료와 무관하게 계속 실행되는 안정 경로를 확보한다.

## 수행 작업
1. 사전 상태 확인
- 실행: `bash scripts/wiki_embeddings_status.sh`
- 시작 기준:
  - `embedded=0`
  - `missing=1002975`

2. 임베딩 런타임 준비
- `ollama` 컨테이너 기동
- `nomic-embed-text` 모델 pull 완료

3. 실백필 시작
- 실행 방식:
  - 초기 foreground 검증으로 정상 처리 확인
  - 이후 backend 컨테이너 내부 detached 프로세스로 전환

4. 처리량 튜닝 적용
- 기존 파라미터:
  - `batch-size=32`, `sleep-ms=150`
- 튜닝 파라미터:
  - `batch-size=64`, `report-every=10`, `timeout-sec=180`, `sleep-ms=0`
- 목적:
  - 장시간 백필 총 소요시간 단축

5. 실행 상태 검증
- `docker top olala-backend`에서 백필 프로세스 확인
- 상태 체크 증가 확인:
  - `embedded=3072` -> `3488` -> `3872`
- 실패 로그 누적: `0`건

## 기존 대비 변경 사항
- 기존:
  - 임베딩 정책/도구만 준비된 상태
- 변경:
  - 실백필을 실제 가동하고 detached 실행 경로로 고정
  - 처리량 튜닝 파라미터 적용
- 효과:
  - 임베딩 생성이 문서 단계가 아니라 실제 운영 단계로 전환
  - 처리량 개선(초기 관측 기준 약 2배 내외)

## 현재 리스크
1. 장시간 처리
- 약 100만 chunk 규모로 완료까지 장시간 소요

2. 처리량 편차
- CPU 부하/컨테이너 상태에 따라 속도 변동 가능

3. 완료 후 전환 미실시
- 완료 후 `WIKI_EMBEDDINGS_READY=true` 전환/재기동/스모크는 아직 미실행

## 다음 단계
- STEP-13: 임베딩 완료 확인 및 운영 전환
  - `missing=0` 확인
  - `.env.beta`에서 `WIKI_EMBEDDINGS_READY=true` 설정
  - `bash scripts/run_beta.sh`
  - `bash scripts/smoke_mobile_bridge.sh`
