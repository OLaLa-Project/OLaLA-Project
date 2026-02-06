# Stage 2: QueryGen (검색 쿼리 생성)

> **담당**: Team A (이윤호, 성세빈)

## 역할

정규화된 텍스트에서 Wikipedia 검색용 쿼리를 생성합니다.

## 입력

```python
{
    "request_id": "uuid",
    "normalized_claim": "정규화된 텍스트",
    "language": "ko"
}
```

## 출력

```python
{
    "request_id": "uuid",
    "queries": [
        {"query": "검색어1", "type": "entity"},
        {"query": "검색어2", "type": "keyword"}
    ]
}
```

## 구현 체크리스트

- [ ] 핵심 키워드 추출
- [ ] 엔티티(인물, 장소, 조직) 추출
- [ ] 다양한 검색 쿼리 생성
- [ ] SLM1을 활용한 쿼리 확장

## 파일 구조

```
stage2_querygen/
├── README.md
├── __init__.py
├── node.py         ← 메인 로직
└── prompts.py      ← LLM 프롬프트
```

## 시작하기

`node.py` 파일의 `querygen_node` 함수를 구현하세요.
