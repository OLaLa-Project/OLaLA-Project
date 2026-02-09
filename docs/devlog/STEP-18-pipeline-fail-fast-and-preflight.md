# STEP-18 Pipeline Fail-Fast and Preflight

- Date: 2026-02-09
- Status: Completed
- Scope: SLM/Stage9 실패 가시화, 사전 점검 자동화, 스모크 신뢰도 강화

## 목표
백엔드가 "응답은 하지만 잘못된 결과"를 내는 상태를 조기에 감지하고, 장애 원인을 로그/응답에서 즉시 식별 가능하게 만든다.

## 수행 작업
1. SLM 클라이언트 오류 분류 강화
- 파일: `services/backend/app/stages/_shared/slm_client.py`
- 변경:
  - OpenAI 호환 경로와 Ollama native 경로를 순차 시도
  - 404 응답에서 `model not found`를 식별해 `SLMModelNotFoundError`로 명시
  - 실패한 URL 시도 이력 포함 에러 메시지 제공

2. 파이프라인 strict 모드 도입
- 파일: `services/backend/app/orchestrator/service.py`
- 변경:
  - `settings.strict_pipeline == true`이면 예외를 fallback 응답으로 삼키지 않고 재전파
  - 베타/운영에서 선택적으로 5xx 노출 가능

3. Stage9 모델 메타 정확화
- 파일: `services/backend/app/stages/stage09_judge/node.py`
- 변경:
  - `model_info.provider`를 base URL 기반으로 추론(`openai/perplexity/anthropic/ollama/custom`)

4. 사전 점검 스크립트 추가
- 파일: `scripts/check_llm_stack.sh` (신규), `scripts/check_stack.sh`
- 변경:
  - SLM1/SLM2/JUDGE 모델 존재 여부 검사
  - 외부 provider 사용 시 `JUDGE_API_KEY` 존재 검사
  - `check_stack.sh`가 하위 실패를 성공으로 숨기지 않고 exit 1 반환하도록 수정

5. 스모크 테스트 실효성 강화
- 파일: `scripts/smoke_mobile_bridge.sh`
- 변경:
  - 단순 경로 접근성(405) 확인에서 실제 `POST /v1/truth/check` 기능 검사로 변경
  - `analysis_id` 누락/핵심 리스크 플래그(`LLM_JUDGE_FAILED` 등) 감지 시 실패 처리

## 기존 대비 변경 사항
- 기존:
  - 모델 미설치/LLM 실패가 모호한 로그 또는 성공처럼 보이는 스모크에 가려짐
  - `check_stack.sh`가 실패를 전파하지 않아 CI/운영 판단이 왜곡될 수 있음
- 변경:
  - 모델 미설치가 명확한 에러로 표출됨
  - 사전 점검/스모크가 실제 장애를 실패 코드로 반환
  - strict 모드로 문제를 즉시 5xx로 드러낼 수 있음

## 검증 결과
1. LLM preflight
- 실행: `bash scripts/check_llm_stack.sh`
- 결과: `gemma3:4b` 미설치 감지(실패)

2. 통합 스택 점검
- 실행: `bash scripts/check_stack.sh`
- 결과: preflight 실패를 반영해 최종 `exit 1` 반환

3. 모바일 브리지 스모크
- 실행: `bash scripts/smoke_mobile_bridge.sh`
- 결과: `/v1/truth/check` 응답은 받았으나 `LLM_JUDGE_FAILED` 감지로 실패 처리

## 남은 리스크
1. Ollama 추론 모델 부재
- 현재 `nomic-embed-text`만 존재, `gemma3:4b` 없음
- Stage1/2/6/7/9 정상 추론 불가

2. 테스트 러너 부재
- 로컬/컨테이너 모두 `pytest` 미설치
- 신규 단위테스트(`services/backend/tests/unit/test_orchestrator_service_strict_pipeline.py`) 자동 검증 미완료

3. 외부 LLM 키 보안
- 외부 키 사용 시 저장 위치/로테이션/마스킹 정책 필요

## 다음 단계
- STEP-19: 인코딩/로그 품질 정리 및 잔여 리스크 최종 점검
