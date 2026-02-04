# OLaLA Frontend - Backend API 연동 가이드

## 📋 개요

이 문서는 Flutter 기반 OLaLA 프론트엔드와 FastAPI 기반 백엔드의 연동 구조 및 사용 방법을 설명합니다.

---

## 🏗️ 아키텍처

```
┌─────────────────────────────────────────────────────────────┐
│                     Flutter Frontend                        │
│                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────┐    │
│  │  Controller  │──▶│   Service    │──▶│  ApiClient  │    │
│  │   (GetX)     │   │   Layer      │   │    (Dio)    │    │
│  └──────────────┘   └──────────────┘   └─────────────┘    │
│                                               │             │
└───────────────────────────────────────────────┼─────────────┘
                                                │
                                         HTTP/REST API
                                                │
┌───────────────────────────────────────────────┼─────────────┐
│                                               ▼             │
│                     FastAPI Backend                         │
│                                                              │
│  ┌──────────────┐   ┌──────────────┐   ┌─────────────┐    │
│  │   Routers    │──▶│   Services   │──▶│  Database   │    │
│  │  (API 엔드포인트)│   │  (Use Cases) │   │ (Postgres)  │    │
│  └──────────────┘   └──────────────┘   └─────────────┘    │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## 📦 구현된 주요 컴포넌트

### 1. 네트워크 레이어 (`lib/shared/network/`)

#### `api_client.dart`
- **Dio 기반 HTTP 클라이언트** (Singleton)
- 자동 로깅 (개발 환경)
- 타임아웃 설정 (30초)
- 인터셉터 지원 (인증, 에러 처리)
- Result 패턴으로 래핑된 응답

```dart
// 사용 예시
final client = ApiClient.instance;
final result = await client.get<Map<String, dynamic>>('/health');
```

#### `api_result.dart`
- **Result 패턴** 구현 (Success/Failure)
- 함수형 프로그래밍 스타일 (`when`, `map`, `flatMap`)
- 타입 안전성 보장

```dart
result.when(
  success: (data) => print('Success: $data'),
  failure: (error) => print('Error: ${error.message}'),
);
```

#### `api_exception.dart`
- **커스텀 예외 처리**
- HTTP 상태 코드별 분류 (400, 401, 404, 422, 500 등)
- FastAPI 검증 에러 자동 파싱
- 사용자 친화적 에러 메시지

---

### 2. 서비스 레이어 (`lib/shared/services/`)

각 도메인별로 API 호출을 담당하는 서비스 클래스:

#### `health_service.dart`
```dart
final healthService = HealthService();
final result = await healthService.checkHealth();
```

#### `truth_check_service.dart`
```dart
final service = TruthCheckService();
final request = TruthCheckRequest(
  inputType: InputType.text,
  inputPayload: '검증할 텍스트',
  language: 'ko',
);
final result = await service.checkTruth(request);
```

#### `wiki_service.dart`
```dart
final wikiService = WikiService();
final request = WikiSearchRequest(
  question: '검색 쿼리',
  topK: 5,
);
final result = await wikiService.search(request);
```

---

### 3. 모델 레이어 (`lib/shared/models/`)

백엔드 스키마와 1:1 매칭되는 Dart 모델:

- `truth_check_model.dart`: 팩트체크 요청/응답
- `wiki_model.dart`: 위키 검색 요청/응답
- `health_model.dart`: 헬스체크 응답

**특징:**
- `fromJson` / `toJson` 직렬화 지원
- Null safety 완전 지원
- 타입 안전성 보장

---

### 4. 환경 설정 (`lib/app/env.dart`)

개발/프로덕션 환경별 설정:

```dart
class Env {
  // 자동으로 환경에 맞는 API URL 반환
  static String get apiBaseUrl {
    if (kDebugMode) {
      if (defaultTargetPlatform == TargetPlatform.android) {
        return 'http://10.0.2.2:8080'; // Android Emulator
      }
      return 'http://localhost:8080'; // iOS Simulator
    } else {
      return 'https://api.olala.com'; // Production
    }
  }
}
```

---

## 🚀 사용 방법

### 1. 패키지 설치

```bash
cd olala_frontend
flutter pub get
```

### 2. Backend 서버 실행

```bash
cd ../backend
docker compose up -d
```

Backend는 `http://localhost:8080`에서 실행됩니다.

### 3. GetX 컨트롤러에서 API 호출

```dart
class MyController extends GetxController {
  final TruthCheckService _service = TruthCheckService();
  final RxBool isLoading = false.obs;

  Future<void> checkFact(String text) async {
    isLoading.value = true;

    final request = TruthCheckRequest(
      inputType: InputType.text,
      inputPayload: text,
    );

    final result = await _service.checkTruth(request);

    result.when(
      success: (response) {
        // 성공 처리
        print('판정: ${response.label.displayName}');
        print('신뢰도: ${response.confidencePercent}');
      },
      failure: (error) {
        // 에러 처리
        Get.snackbar('오류', error.message);
      },
    );

    isLoading.value = false;
  }
}
```

---

## 🔌 API 엔드포인트 목록

| 메서드 | 엔드포인트 | 설명 | 서비스 |
|--------|-----------|------|--------|
| GET | `/health` | 서버 상태 확인 | `HealthService` |
| POST | `/truth/check` | 팩트체크 (일반) | `TruthCheckService` |
| POST | `/api/truth/check/stream` | 팩트체크 (스트리밍) | `TruthCheckService` |
| POST | `/api/wiki/search` | 위키 시맨틱 검색 | `WikiService` |
| POST | `/api/wiki/keyword-search` | 위키 키워드 검색 | `WikiService` |

---

## 🧪 테스트

### 헬스체크 테스트

```dart
void testHealthCheck() async {
  final service = HealthService();
  final result = await service.checkHealth();

  result.when(
    success: (health) {
      print('✅ 서버 상태: ${health.status}');
      assert(health.isHealthy);
    },
    failure: (error) {
      print('❌ 에러: ${error.message}');
    },
  );
}
```

### 팩트체크 테스트

```dart
void testTruthCheck() async {
  final service = TruthCheckService();
  final request = TruthCheckRequest(
    inputType: InputType.text,
    inputPayload: '지구는 평평하다',
  );

  final result = await service.checkTruth(request);

  result.when(
    success: (response) {
      print('✅ 판정: ${response.label.displayName}');
      print('   신뢰도: ${response.confidencePercent}');
      print('   요약: ${response.summary}');
    },
    failure: (error) {
      print('❌ 에러: ${error.message}');
    },
  );
}
```

---

## 🛠️ 개발 환경별 설정

### iOS 시뮬레이터
- `http://localhost:8080` 사용
- 별도 설정 불필요

### Android 에뮬레이터
- `http://10.0.2.2:8080` 사용 (자동 적용)
- 10.0.2.2는 호스트 머신의 localhost를 가리킴

### 실제 기기 (USB 디버깅)
- 호스트 머신의 IP 주소 사용
- `env.dart`에서 수동 설정 필요:
  ```dart
  return 'http://192.168.x.x:8080';
  ```

---

## 🔐 CORS 설정

Backend의 CORS는 개발 환경에서 모든 origin을 허용하도록 설정되어 있습니다:

```python
# backend/app/main.py
cors_origins = ["*"]  # 개발 환경
```

**프로덕션 배포 시 주의:**
- 환경변수 `CORS_ORIGINS`로 특정 도메인만 허용
- 예: `CORS_ORIGINS=https://olala.com,https://app.olala.com`

---

## 📝 실무 모범 사례

### ✅ DO (권장)

1. **Result 패턴 사용**
   ```dart
   result.when(
     success: (data) => handleSuccess(data),
     failure: (error) => handleError(error),
   );
   ```

2. **로딩 상태 관리**
   ```dart
   isLoading.value = true;
   await apiCall();
   isLoading.value = false;
   ```

3. **에러 메시지 사용자에게 표시**
   ```dart
   failure: (error) => Get.snackbar('오류', error.message)
   ```

### ❌ DON'T (비권장)

1. **Raw Dio 인스턴스 직접 사용**
   ```dart
   // ❌ 나쁜 예
   final dio = Dio();
   await dio.get('http://localhost:8080/health');

   // ✅ 좋은 예
   final service = HealthService();
   await service.checkHealth();
   ```

2. **에러 무시**
   ```dart
   // ❌ 나쁜 예
   try { await apiCall(); } catch(e) {}

   // ✅ 좋은 예
   result.onFailure((error) => handleError(error));
   ```

---

## 🐛 트러블슈팅

### 1. "Connection refused" 에러
- Backend 서버가 실행 중인지 확인
- `curl http://localhost:8080/health` 테스트

### 2. Android 에뮬레이터에서 연결 안됨
- `10.0.2.2` 사용 확인 (자동 적용됨)
- 방화벽 설정 확인

### 3. CORS 에러
- Backend의 CORS 설정 확인
- 개발 환경에서는 `"*"` 허용

### 4. 타임아웃 에러
- 네트워크 연결 확인
- `Env.connectTimeout` 값 증가 (필요시)

---

## 📚 추가 참고 자료

- [Dio 공식 문서](https://pub.dev/packages/dio)
- [GetX 공식 문서](https://pub.dev/packages/get)
- [FastAPI 공식 문서](https://fastapi.tiangolo.com/)

---

## 👤 담당자

- **Frontend**: Flutter 팀
- **Backend**: FastAPI 팀
- **연동 이슈**: GitHub Issues 등록

---

**작성일**: 2026-02-03
**버전**: 1.0.0
