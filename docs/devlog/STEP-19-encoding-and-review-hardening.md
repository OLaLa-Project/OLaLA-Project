# STEP-19 Encoding and Review Hardening

- Date: 2026-02-09
- Status: Completed
- Scope: 한글/코드 깨짐 점검, 로그 품질 정리, 잔여 코드리뷰 리스크 명문화

## 목표
문자 인코딩 및 불필요 디버그 출력으로 인한 운영 리스크를 줄이고, 현재 코드베이스의 남은 구조적 리스크를 우선순위로 정리한다.

## 수행 작업
1. 인코딩 깨짐 점검
- 실행:
  - `rg -n "�" --glob '!**/.git/**'`
  - `git ls-files | ... grep $'\\xEF\\xBB\\xBF'`
- 조치:
  - `services/backend-monorepo/backend/app/stages/_shared/slm_client.py`의 UTF-8 BOM 제거

2. 로그 품질 정리
- 파일:
  - `services/backend/app/stages/stage03_collect/node.py`
  - `services/backend/app/services/wiki_usecase.py`
- 변경:
  - 운영 경로의 다수 `print` 디버그를 logger 호출로 통일

3. 잔여 디버그 출력 위치 식별
- 실행: `rg -n "print\\(" services/backend/app`
- 결과:
  - `services/backend/app/debug_db.py`
  - `services/backend/app/tools/wiki_embeddings_backfill.py`
- 판단: 개발/도구성 파일로 분류(운영 경로와 분리되어 있음)

## 기존 대비 변경 사항
- 기존:
  - 일부 경로에 BOM 존재
  - 운영 코드에 콘솔 `print`가 혼재
- 변경:
  - BOM 제거 완료
  - 운영 경로 로깅을 logger 중심으로 통일
  - 남은 `print` 위치를 명시적으로 식별/분류

## 검증 결과
1. BOM 재검사
- 실행: `git ls-files | ... grep $'\\xEF\\xBB\\xBF'`
- 결과: 매치 없음

2. 깨짐 문자 검사
- 실행: `rg -n "�" --glob '!**/.git/**'`
- 결과: 매치 없음

## 남은 리스크
1. 이중 백엔드 트리 운영 리스크
- `services/backend`와 `services/backend-monorepo/backend` 간 동일 파일 분기 존재
- 수정 누락/드리프트 가능성 높음

2. 외부 API 키 유출 리스크
- 노출된 Judge 키는 즉시 폐기(rotate) 필요
- 평문 `.env` 저장 대신 시크릿 매니저/주입 파이프라인 권장

3. 외부 검색 API 크리덴셜 공란
- `.env.beta`의 `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`가 비어 있어 Naver 검색 경로 품질 저하 가능

## 다음 단계
- 모델 공급 전략 확정:
  - A안: Ollama `gemma3:4b` 설치/검증
  - B안: Stage9 외부 LLM(API key)로 전환 후 strict 모드에서 재스모크
