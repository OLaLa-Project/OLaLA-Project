# Wiki Embeddings Batch Policy

## 목적
`public.wiki_chunks.embedding` 누락 데이터를 안정적으로 채우고, 운영 중단/재개가 가능한 표준 절차를 고정한다.

## 전제 조건
1. 베타 스택 기동: `bash scripts/run_beta.sh`
2. wiki DB 적재 완료: `bash scripts/import_wiki_db.sh`
3. 임베딩 모델 접근 가능
- 기본: `OLLAMA_URL=http://ollama:11434`
- 주의: `scripts/wiki_embeddings_backfill.sh`는 기본적으로 ollama 컨테이너를 자동 기동하지 않는다.
- 내부 ollama를 함께 올릴 때만 `OLALA_START_OLLAMA=1`(또는 `--with-ollama`)을 명시한다.

## 운영 모드
### 1) Bootstrap 모드 (최초 대량 백필)
전체 누락 임베딩을 채우는 1회성 작업.

권장 실행:
```bash
OLALA_START_OLLAMA=1 bash scripts/wiki_embeddings_backfill.sh \
  --batch-size 64 \
  --report-every 10 \
  --timeout-sec 120 \
  --sleep-ms 150 \
  --max-chars 2000 \
  --failure-log /tmp/wiki-embed-failures-bootstrap.jsonl
```

권장 이유:
- `batch-size 64`: 처리량/실패 격리 균형
- `sleep-ms 150`: Ollama 과부하 완화
- `failure-log`: 재처리 대상 분리

### 2) Maintenance 모드 (증분 백필)
신규 chunk 유입 이후 주기적으로 누락분만 보충.

권장 실행:
```bash
bash scripts/wiki_embeddings_backfill.sh \
  --batch-size 32 \
  --max-chunks 20000 \
  --report-every 20 \
  --timeout-sec 120 \
  --sleep-ms 100 \
  --failure-log /tmp/wiki-embed-failures-maintenance.jsonl
```

## 상태/중단/재개
상태 확인:
```bash
bash scripts/wiki_embeddings_status.sh
```

중단 요청(안전 중단):
```bash
bash scripts/wiki_embeddings_stop.sh
```

재개:
```bash
bash scripts/wiki_embeddings_resume.sh
```

참고:
- `stop`은 현재 배치 종료 후 루프가 멈추는 방식이다.
- stop 파일 기본값: `/tmp/wiki-embed.stop` (`EMBED_STOP_FILE`로 변경 가능)

## 실패 처리
1. 실패 chunk 기록 확인:
```bash
cat /tmp/wiki-embed-failures-bootstrap.jsonl
```
2. 원인 분류:
- 모델 응답 실패/타임아웃
- 특수 텍스트로 인한 요청 실패
3. 조치:
- `--batch-size` 축소 (예: 64 -> 16)
- `--timeout-sec` 증가
- `--max-chars` 축소
- 실패 로그 기반 재실행

## 완료 판정
완료 기준:
- `missing=0`
- `coverage_pct=100.00`

완료 후 전환:
1. `.env.beta`에서 `WIKI_EMBEDDINGS_READY=true` 설정
2. 백엔드 재시작
```bash
bash scripts/run_beta.sh
```
3. 확인
```bash
bash scripts/wiki_embeddings_status.sh
```

## 운영 리스크
1. 대량 백필 시간 리스크
- 백만 건 단위는 장시간 소요될 수 있음

2. 모델/이미지 준비 리스크
- 내부 ollama를 opt-in으로 시작할 때 첫 실행에서 이미지 pull(수 GB) 시간이 필요할 수 있음

3. 품질 리스크
- 임베딩 모델 교체 시 검색 품질 변동 가능
- 모델 변경 시 전량 재백필 정책 필요
