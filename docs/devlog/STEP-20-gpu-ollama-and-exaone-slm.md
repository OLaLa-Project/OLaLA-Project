# STEP-20 GPU Ollama and EXAONE SLM

- Date: 2026-02-09
- Status: Completed
- Scope: Ollama GPU 추론 활성화 + SLM 모델을 EXAONE 8B 계열로 전환

## 목표/범위
- SLM(Stage1~2, Stage6~7) 호출이 CPU 병목에 걸리지 않도록 Ollama를 GPU 경로로 구동한다.
- SLM 기본 모델을 EXAONE 8B 계열(`exaone3.5:7.8b`)로 맞춘다.

## 수행 작업
1. Ollama GPU 설정 반영
- 파일: `infra/docker/docker-compose.beta.yml`
- 변경:
  - `ollama` 서비스에 `gpus: all` 추가
  - `NVIDIA_VISIBLE_DEVICES=all`, `NVIDIA_DRIVER_CAPABILITIES=compute,utility` 추가

2. SLM 모델 EXAONE으로 전환
- 파일: `.env.example`
- 변경:
  - `SLM1_MODEL=exaone3.5:7.8b`
  - `SLM2_MODEL=exaone3.5:7.8b`

3. 모델 다운로드 및 동작 확인
- 실행:
  - `docker exec olala-ollama ollama pull exaone3.5:7.8b`
  - `docker exec olala-ollama ollama run exaone3.5:7.8b "안녕하세요..."`
- 확인:
  - Ollama 로그에서 CUDA backend 로드 및 레이어 GPU offload 메시지 확인
  - 한국어 응답 정상 출력 확인

## 변경 사항(기존 대비)
- 기존: CPU 기반 추론으로 응답 지연이 길어질 수 있음
- 변경: GPU 추론 경로(CUDA)로 실행되어 지연/처리량 개선 여지 확보

## 검증 결과
- `docker logs olala-ollama`에서 CUDA backend 로드 및 GPU(offload) 메시지 확인
- `ollama run exaone3.5:7.8b` 응답 정상

## 남은 리스크
- GPU 런타임 의존성:
  - Docker/NVIDIA Container Toolkit 구성에 따라 `gpus: all`이 무시되거나 실패할 수 있음
- VRAM 사용량:
  - EXAONE 8B 계열은 메모리 압박이 있을 수 있어 동시성/컨텍스트 길이에 따라 OOM 가능
- Stage9 Judge 품질:
  - Judge를 로컬 모델로 운용 시 모델 품질/프롬프트 튜닝 이슈가 남음(외부 LLM 전환 고려)

## 다음 단계
- Stage9 외부 LLM(JUDGE) 키 주입/운영 정책 확정(Perplexity/OpenAI 등)
- LangGraph 체크포인트(PostgresSaver) 의존성 보강 및 운영 DB 기반으로 안정화

