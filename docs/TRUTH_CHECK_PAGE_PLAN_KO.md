# Truth Check 페이지 단계별 출력 플랜 (한글)

## 목적
- `web/truth-check` 페이지에서 gateway + LangGraph 기반 파이프라인의 stage별 결과를 순차적으로 보여준다.
- 스트리밍 응답을 “로그 나열”이 아니라 “단계별 상태 + 결과”로 구조화해 사용자 이해도를 높인다.

## 현재 상태 요약
- `web/src/pages/truth-check/TruthCheckPage.tsx`는 `/api/truth/check/stream` 응답을 줄 단위로 그대로 출력한다.
- stage 구분, 진행 상태, 실패 지점 표시 등이 없다.

## 요구사항 정리
- stage 순서대로 출력되며, 각 stage의 상태가 즉시 갱신된다.
- stage별 결과 요약과 원문(옵션)을 분리해 보여준다.
- 중간 실패 시에도 이미 완료된 stage는 유지되고, 실패 stage를 명확히 표시한다.
- 취소(Abort) 동작 시 상태를 중단으로 표기한다.

## 데이터 모델(초안)
- `StageId`: `stage01_normalize` ~ `stage09_judge`
- `StageStatus`: `idle` | `running` | `success` | `error` | `aborted`
- `StageResult`:
  - `id`: StageId
  - `label`: 사용자 표시용 이름
  - `status`: StageStatus
  - `startedAt`, `endedAt` (옵션)
  - `summary`: 핵심 요약 텍스트
  - `detail`: 원문/JSON 등 원자료(접기 가능)
  - `errorMessage` (옵션)
- `PipelineRun`:
  - `runId` (옵션)
  - `input`: claim
  - `stages`: StageResult[]
  - `overallStatus`: `running` | `success` | `error` | `aborted`

## 스트리밍 파싱/매핑 전략
- 현재는 라인 텍스트 기반 스트리밍이므로, 아래 중 하나로 표준화 필요
  - (A) 백엔드가 stage 이벤트 JSON을 라인 단위로 emit
  - (B) 프론트에서 기존 라인을 stage 이벤트로 파싱하는 규칙 정의
- 추천: (A) 라인 단위 JSON (SSE 유사)
  - 예시 이벤트 스키마(라인 JSON):
    - `{"type":"stage_start","stage":"stage03_search","ts":"..."}`
    - `{"type":"stage_output","stage":"stage03_search","summary":"...","detail":{...}}`
    - `{"type":"stage_end","stage":"stage03_search","status":"success"}`
    - `{"type":"stage_error","stage":"stage03_search","message":"..."}`
    - `{"type":"pipeline_end","status":"success"}`

## UI/UX 구성(초안)
- 상단: 입력 영역(Claim), 실행 버튼, 취소 버튼
- 중앙: 전체 진행 상태(현재 단계명, 진행률, 전체 상태 배지)
- 하단: stage 리스트(세로)
  - 각 stage 카드: 상태 아이콘 + 단계명 + 요약
  - 클릭 시 detail 확장(원문/JSON)
  - 실패 시 빨간 강조 + 오류 메시지 고정 노출
- 빈 상태: “실행 준비됨”
- 로딩 상태: 현재 stage 강조, 이전 stage는 성공 표시

## 상태 전이 규칙
- 실행 시작 시 모든 stage `idle`, 첫 stage `running`
- `stage_start` 수신 시 해당 stage `running`
- `stage_output` 수신 시 summary/detail 누적 또는 마지막 값 갱신
- `stage_end` 수신 시 `success` 또는 `error`
- `stage_error` 수신 시 해당 stage `error`, 파이프라인 `error`
- Abort 시 `aborted`로 마감, 진행 중 stage를 `aborted`로 표기

## API/백엔드 확인 포인트
- `/api/truth/check/stream`의 이벤트 형식 확정 필요
- stage별 label/설명 매핑 테이블 제공 여부
- `include_full_outputs`, `start_stage`, `end_stage` 파라미터 유지 여부
- runId/traceId 제공 가능 여부
- 현재 구현은 graph가 `stage_complete/error/complete` JSON 라인 이벤트를 생성하고,
  gateway(API)는 별도 가공 없이 스트림을 그대로 전달하는 pass-through 구조
- gateway의 요약 생성/가공 책임은 추후 진행(현재는 graph 출력 그대로 전달)

## 구현 작업 항목(프론트)
1. stage 메타데이터(순서, 라벨) 정의
2. `PipelineRun` 상태 모델 추가
3. 스트리밍 파서 구현(JSON 라인 기반 가정)
4. stage 카드 UI 컴포넌트 분리
5. 진행률/전체 상태 표시 컴포넌트
6. 에러/중단 처리 및 재실행 흐름 정리

## 테스트/검증 체크리스트
- 정상 흐름: 1~9단계 순차 표시
- 중간 실패: 실패 단계 표시 + 이후 단계 미진행
- Abort: 즉시 중단 표시 + 버튼 상태 복원
- 빠른 재실행: 이전 run 상태 초기화
- 대용량 detail: UI 성능 및 접기 동작 확인

## 다음 확인 사항(질문)
- 실제 gateway/graph에서 stage 이벤트 형식을 어떻게 보낼 계획인가?
- stage별 요약 텍스트의 책임(백엔드 vs 프론트)은 어디로 둘 것인가?
- 결과 JSON을 그대로 보여줄지, 스키마 기반 요약으로 가공할지?
