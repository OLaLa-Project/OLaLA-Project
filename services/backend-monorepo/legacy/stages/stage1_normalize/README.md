# Stage 1: Normalize (텍스트 정규화)

> **담당**: Team A (이윤호, 성세빈)

## 역할

사용자 입력 텍스트를 정규화하여 다음 Stage로 전달합니다.

## 입력

```python
{
    "request_id": "uuid",
    "raw_claim": "사용자가 입력한 원본 텍스트"
}
```

## 출력

```python
{
    "request_id": "uuid",
    "normalized_claim": "정규화된 텍스트",
    "language": "ko",  # 감지된 언어
    "metadata": {}
}
```

## 구현 체크리스트

- [ ] 특수문자 제거/정규화
- [ ] 공백 정리
- [ ] 언어 감지
- [ ] 너무 짧거나 긴 입력 처리

## 파일 구조

```
stage1_normalize/
├── README.md       ← 지금 보는 파일
├── __init__.py
├── node.py         ← 메인 로직 (여기서 작업!)
└── utils.py        ← 유틸리티 함수
```

## 시작하기

`node.py` 파일의 `normalize_node` 함수를 구현하세요:

```python
def normalize_node(state: dict) -> dict:
    # TODO: 구현
    pass
```
