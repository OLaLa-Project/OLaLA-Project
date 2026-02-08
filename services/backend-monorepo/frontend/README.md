# Frontend (Flutter)

## 역할
모바일 앱 UI를 담당합니다.
- 입력 화면 (URL/TEXT)
- 결과 카드 화면
- 피드백 UI

## 작업 위치
- UI: `frontend/lib/`
- 메인 엔트리: `frontend/lib/main.dart`
- 홈 화면: `frontend/lib/screens/home_screen.dart`
- API 연동: `frontend/lib/services/api_service.dart`
- 응답 모델: `frontend/lib/models/verification_result.dart`

## API 계약(최종 결과 스키마)
프론트는 아래 필드만 믿고 렌더링합니다.
- `analysis_id`, `label`, `confidence`, `summary`
- `citations[]`, `limitations[]`, `recommended_next_steps[]`

계약 문서: `docs/CONTRACT.md`

## 실행 방법
```bash
flutter pub get
flutter run
```

## 주의사항
- API 스키마를 임의로 바꾸지 마세요.
- 결과 카드 UI는 계약(JSON)을 그대로 렌더링해야 합니다.
