# Colab GPU Embedding Workflow

## 핵심
- Colab은 기본적으로 PostgreSQL 서버를 제공하지 않습니다.
- 권장 방식: `로컬 DB에서 CSV 추출 -> Colab GPU 임베딩 -> 로컬 DB 반영`.

## 0) 환경값 (현재 프로젝트)
- `EMBED_MODEL=dragonkue/multilingual-e5-small-ko-v2`
- `EMBED_DIM=384`

## 1) 로컬 DB에서 임베딩 대상 CSV 추출
프로젝트 루트에서:

```bash
cd /home/se/workspace/OLaLA-Project
python3 scripts/export_wiki_chunks_for_colab.py
```

생성 파일: `wiki_chunks.csv`

## 2) Colab GPU에서 임베딩 생성
Colab 파일 업로드:
- `scripts/colab_embedding_gen.py`
- `wiki_chunks.csv`

Colab 셀:

```bash
!pip -q install sentence-transformers pandas pyarrow fastparquet tqdm
```

```bash
!EMBED_MODEL=dragonkue/multilingual-e5-small-ko-v2 EMBED_DIM=384 \
 python colab_embedding_gen.py
```

생성 파일: `new_embeddings.parquet`

## 3) 로컬로 parquet 다운로드 후 DB 반영
프로젝트 루트에 `new_embeddings.parquet`를 둔 뒤:

```bash
cd /home/se/workspace/OLaLA-Project
EMBED_DIM=384 COLAB_IMPORT_DB_HOST=localhost COLAB_IMPORT_DB_PORT=5432 \
python3 scripts/import_colab_embeddings.py
```

## 4) 반영 확인

```bash
docker compose exec -T db psql -U postgres -d olala -c "
SELECT COUNT(*) AS total,
       COUNT(embedding) AS with_embedding,
       COUNT(*) - COUNT(embedding) AS without_embedding
FROM wiki_chunks;
"
```
