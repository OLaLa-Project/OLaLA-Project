# MLOps

## 역할
학습/평가/모델 설정을 담당합니다.

## 폴더 구조
- `mlops/training/`  : Colab 노트북, 학습 스크립트
- `mlops/eval/`      : 평가 데이터 및 스크립트
- `mlops/models/`    : 모델 설정 (가중치 커밋 금지)
- `mlops/requirements.txt` : ML 의존성

## 팀 작업 규칙
- 모델 가중치/대형 데이터는 **절대 커밋 금지**
- 필요한 경우 `models/README.md`에 다운로드 방법만 기록
