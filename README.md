# OLaLA MVP

OLaLA??硫???먯씠?꾪듃 湲곕컲 媛吏쒕돱???먮룆 MVP?낅땲?? ???덊룷??**?꾨줎??Flutter) / 諛깆뿏??FastAPI) / MLOps**瑜???怨녹뿉 紐⑥? **紐⑤끂?덊룷**?낅땲??

## ?ъ쟾 以鍮????몄뒪??Ollama

SLM? Docker 而⑦뀒?대꼫媛 ?꾨땶 **?몄뒪??癒몄떊**?먯꽌 ?ㅽ뻾 以묒씤 Ollama瑜??ъ슜?⑸땲??

```bash
# Ollama ?ㅼ튂: https://ollama.com
ollama pull qwen2.5:3b        # 紐⑤뜽 ?ㅼ슫濡쒕뱶
ollama list                   # qwen2.5:3b ?뺤씤
```

## 鍮좊Ⅸ ?쒖옉

```bash
cp .env.example .env                   # ?섍꼍蹂??(.env.example 湲곕낯媛?洹몃?濡??ъ슜 媛??
docker compose up -d --build           # api + db ?ㅽ뻾 (Ollama 而⑦뀒?대꼫 ?놁쓬)
curl http://localhost:8000/health      # ?ъ뒪泥댄겕
```

## SLM2 테스트 (Stage 6-7 + Stage 8 Aggregator)

```bash
# 湲곕낯 ?ㅽ뻾 (耳?댁뒪 #1)
docker compose --profile test run --rm slm2-test

# ?뱀젙 耳?댁뒪 吏??
docker compose --profile test run --rm -e CASE=2 slm2-test

# ?꾩껜 耳?댁뒪 ?ㅽ뻾
docker compose --profile test run --rm -e ALL=1 slm2-test

# 濡쒖뺄 mock ?뚯뒪??(Ollama 遺덊븘??
cd backend && python -m tests.test_slm2_stages
```

## 紐⑤뜽 蹂寃?

`.env`에서 SLM1/SLM2/JUDGE 모델을 설정합니다.

```bash
# .env (예시)
SLM1_MODEL=gemma3:4b       # Stage1~2 (SLM1)
SLM2_MODEL=Qwen3-4B        # Stage6~7 (SLM2)
JUDGE_MODEL=gpt-4.1        # Stage9 (LLM)
JUDGE_BASE_URL=https://api.openai.com/v1
JUDGE_API_KEY=<your_openai_api_key>

# 인스턴스에 pull
ollama pull <모델명>
```

## ?붾젆?좊━ 援ъ“
- `frontend/`  Flutter 紐⑤컮????
- `backend/`   FastAPI + Stage ?뚯씠?꾨씪??
- `mlops/`     ?숈뒿/?됯?/紐⑤뜽 ?ㅼ젙
- `shared/`    怨듯넻 ?ㅽ궎留?
- `docs/`      ? 媛?대뱶/怨꾩빟/臾몄꽌
- `legacy/`    怨쇨굅 珥덉븞(?섏젙 湲덉?)

## ?蹂??묒뾽 ?꾩튂
- ? A (Stage 1~5): `backend/app/stages/stage01_normalize` ~ `stage05_topk`
- 팀 B (Stage 6~7): `backend/app/stages/stage06_verify_support` ~ `stage07_verify_skeptic`
- Aggregator (Stage 8): `backend/app/stages/stage08_aggregate`
- 怨듯넻 (Stage 9~10 + ?ㅽ궎留?: `backend/app/stages/stage09_judge`, `stage10_policy`, `shared/`

## 釉뚮옖移??뺤콉 (2媛쒕쭔 ?ъ슜)
- `main`: 理쒖쥌 ?곕え/諛쒗몴??(吏곸젒 ?묒뾽 湲덉?)
- `sub`: ? ?묒뾽 ?듯빀 釉뚮옖移?(紐⑤뱺 ?묒뾽? sub??諛섏쁺)

?묒뾽 諛⑸쾿? `docs/HOW_TO_GIT.md`瑜?李멸퀬?섏꽭??
