# OLaLA 단계별 진행표

## Phase 0 - 통합 골격
- [x] 바탕화면 신규 통합 폴더 생성
- [x] 프론트/백엔드/DB 원본 이관
- [x] 루트 실행 구조(`apps/services/infra/scripts/docs`) 고정
- [x] `.env.example`/compose/스크립트 기본 세팅

## Phase 1 - Flutter + Backend API 계약 고정
- [x] 모바일 호환 REST/WS 계약 문서 고정
- [x] 백엔드 `/v1/issues`, `/v1/chat`, `/v1/chat/messages` 구현
- [x] Flutter verify를 Mock -> API 저장소로 전환
- [x] `dart-define` 환경 분리(dev/beta/prod)

## Phase 2 - Wiki DB Docker 운영
- [x] wiki CSV 적재 자동화 검증
- [x] 인덱스/성능 기준 정리
- [x] 임베딩 배치 정책 수립

## Phase 3 - WSL 베타 릴리스
- [x] 베타 스택 안정화
- [x] Android 베타 산출물(APK/AAB) 생성
- [x] 베타 릴리스 번들 준비
- [x] 프론트-백엔드 통합 스모크 검증
- [x] 프로덕션 하드닝 점검 + 빌드 테스트
- [ ] GitHub Pre-release 배포
- [x] Firebase 무료 경로(선택) 정리
