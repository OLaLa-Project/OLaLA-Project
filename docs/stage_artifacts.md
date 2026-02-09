# Truth Check Stage Artifact Logs

각 stage 종료 시 아래 경로에 AI 비교/분석용 아티팩트가 저장됩니다.

- 실행(run) 단위 stage 파일: `<log_dir>/pipeline_artifacts/<YYYYMMDDTHHMMSS.ffffffZ>__<trace_id>/<stage>.json`
- 실행(run) 단위 누적: `<log_dir>/pipeline_artifacts/<YYYYMMDDTHHMMSS.ffffffZ>__<trace_id>/stage_artifacts.jsonl`
- 날짜 정렬 파일: `<log_dir>/pipeline_artifacts/by_date/YYYY-MM-DD/<YYYYMMDDTHHMMSS.ffffffZ>__<trace_id>__<stage>.json`
- 최신 포인터: `<log_dir>/pipeline_artifacts/latest_artifact.json`
- 전체 인덱스: `<log_dir>/pipeline_artifacts/artifact_index.jsonl`
- stage 요약 로그: `<log_dir>/pipeline/<trace_id>_<stage>.json`

기본 `log_dir`는 `Settings.log_dir` (`/app/logs`) 입니다.

## 최신 로그 빠르게 찾기

```bash
# 최신 1건 (가장 최근 stage artifact)
cat storage/logs/backend/pipeline_artifacts/latest_artifact.json

# 오늘 날짜 아티팩트 최신 20건 (파일명 자체가 시간순 정렬 키)
ls -1 storage/logs/backend/pipeline_artifacts/by_date/$(date -u +%F) | tail -n 20

# 전체 인덱스에서 최신 20건
tail -n 20 storage/logs/backend/pipeline_artifacts/artifact_index.jsonl
```

## Artifact 스키마 (`truthcheck.stage_artifact.v1`)

```json
{
  "schema_version": "truthcheck.stage_artifact.v1",
  "trace_id": "string",
  "stage": "stage02_querygen",
  "timestamp": "ISO-8601",
  "duration_ms": 123,
  "llm": {
    "prompt_user": "string",
    "prompt_system": "string",
    "slm_raw": "string",
    "prompt_user_sha256": "hex",
    "prompt_system_sha256": "hex",
    "slm_raw_sha256": "hex",
    "has_llm_io": true
  },
  "stage_json": {},
  "guardrail_hints": {
    "stage06_diagnostics.parse_ok": true,
    "stage06_diagnostics.parse_retry_used": false,
    "stage07_diagnostics.citation_valid_count": 1,
    "stage09_diagnostics.schema_mismatch": false,
    "stage09_diagnostics.fail_closed": false,
    "risk_flags": []
  },
  "comparison_hints": {
    "stage_json_keys": [],
    "stage_json_sha256": "hex",
    "stage_json_key_count": 0,
    "llm_present": true
  }
}
```

## 분석 권장 방식

1. `stage_artifacts.jsonl`를 trace별로 로드해 stage 순서대로 비교합니다.
2. `comparison_hints.stage_json_sha256`로 stage JSON 변경 여부를 빠르게 탐지합니다.
3. `llm.*_sha256`로 프롬프트/원문 응답 변화량을 감지합니다.
4. `guardrail_hints`로 파싱/스키마/fail-closed 상태를 우선 확인합니다.
5. 차이가 있는 stage만 `prompt_user`, `prompt_system`, `slm_raw`, `stage_json`를 정밀 diff 합니다.
