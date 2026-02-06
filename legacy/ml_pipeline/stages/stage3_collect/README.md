# Stage 3: Collect (증거 수집)

> **담당**: Team A (이윤호, 성세빈)

## 역할
Wikipedia에서 관련 증거를 수집합니다 (RAG).

## 입력/출력

| 구분 | 필드 | 설명 |
|------|------|------|
| 입력 | `queries` | 검색 쿼리 리스트 |
| 출력 | `evidences` | 증거 리스트 |

## 증거 형식

```python
{
    "source": "wikipedia",
    "title": "문서 제목",
    "content": "관련 내용",
    "url": "https://..."
}
```

## 구현 체크리스트

- [ ] Wikipedia API 연동
- [ ] BM25 검색 구현
- [ ] Vector 검색 구현
- [ ] Hybrid Search 통합
- [ ] 청킹(Chunking) 전략

## 작업 파일

`node.py`의 `collect_node` 함수를 구현하세요.
