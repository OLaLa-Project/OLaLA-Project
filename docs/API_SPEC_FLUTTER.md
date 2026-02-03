# OLaLa Truth Check API - Flutter Integration Guide

> **Version**: v1.0  
> **Last Updated**: 2026-02-04  
> **Base URL**: `http://localhost:8000` (개발), `https://api.olala.com` (프로덕션)

---

## 📋 목차
1. [개요](#개요)
2. [인증](#인증)
3. [엔드포인트](#엔드포인트)
4. [요청/응답 스키마](#요청응답-스키마)
5. [에러 처리](#에러-처리)
6. [Flutter 통합 예제](#flutter-통합-예제)

---

## 개요

OLaLa Truth Check API는 뉴스 기사, URL, 텍스트 주장의 팩트체크를 수행하는 RESTful API입니다.

### 주요 기능
- ✅ URL 기반 기사 분석
- ✅ 텍스트 주장 검증
- ✅ 실시간 스트리밍 (SSE)
- ✅ 모바일 최적화 (경량 응답)

---

## 인증

현재 버전은 인증이 필요하지 않습니다. (향후 API Key 추가 예정)

---

## 엔드포인트

### 1. 동기식 분석 (Synchronous)

```http
POST /truth/check
Content-Type: application/json
```

**사용 시나리오**: 전체 분석 결과를 한 번에 받고 싶을 때

**요청 예시**:
```json
{
  "input_type": "url",
  "input_payload": "https://news.example.com/article/12345",
  "language": "ko",
  "include_full_outputs": false
}
```

**응답**: [`TruthCheckResponse`](#truthcheckresponse) 참조

---

### 2. 스트리밍 분석 (Streaming - SSE)

```http
POST /api/truth/check/stream
Content-Type: application/json
Accept: text/event-stream
```

**사용 시나리오**: 분석 진행 상황을 실시간으로 UI에 표시하고 싶을 때 (권장)

**요청 예시**:
```json
{
  "input_type": "text",
  "input_payload": "삼성전자가 2024년 1분기 영업이익 6조원을 기록했다",
  "language": "ko",
  "include_full_outputs": false
}
```

**응답 이벤트 스트림**:
```json
// 이벤트 1: 정규화 완료
{"event": "stage_complete", "stage": "stage01_normalize", "data": {"claim_text": "..."}}

// 이벤트 2: 검색 쿼리 생성
{"event": "stage_complete", "stage": "stage02_querygen", "data": {"search_queries": [...]}}

// 이벤트 3: 증거 수집
{"event": "stage_complete", "stage": "stage03_merge", "data": {"evidence_count": 15}}

// ...

// 최종 이벤트: 분석 완료
{"event": "complete", "data": { /* TruthCheckResponse */ }}
```

**에러 이벤트**:
```json
{
  "event": "error",
  "data": {
    "code": "TIMEOUT",
    "stage": "stage03_wiki",
    "message": "Wiki search timeout after 30s",
    "display_message": "분석 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요."
  }
}
```

---

## 요청/응답 스키마

### TruthCheckRequest

| 필드 | 타입 | 필수 | 기본값 | 설명 |
|------|------|------|--------|------|
| `input_type` | `"url" \| "text" \| "image"` | ✅ | `"text"` | 입력 유형 |
| `input_payload` | `string` | ✅ | - | URL 또는 텍스트 내용 |
| `user_request` | `string` | ❌ | `null` | 사용자의 추가 요청사항 |
| `language` | `string` | ❌ | `"ko"` | 언어 코드 (`ko`, `en`) |
| `include_full_outputs` | `boolean` | ❌ | `false` | 디버그 데이터 포함 여부 (모바일은 `false` 권장) |

**Flutter 예시**:
```dart
class TruthCheckRequest {
  final String inputType;
  final String inputPayload;
  final String? userRequest;
  final String language;
  final bool includeFullOutputs;

  TruthCheckRequest({
    required this.inputType,
    required this.inputPayload,
    this.userRequest,
    this.language = 'ko',
    this.includeFullOutputs = false,
  });

  Map<String, dynamic> toJson() => {
    'input_type': inputType,
    'input_payload': inputPayload,
    'user_request': userRequest,
    'language': language,
    'include_full_outputs': includeFullOutputs,
  };
}
```

---

### TruthCheckResponse

| 필드 | 타입 | 설명 |
|------|------|------|
| `analysis_id` | `string` | 분석 고유 ID (추적용) |
| `label` | `"TRUE" \| "FALSE" \| "MIXED" \| "UNVERIFIED" \| "REFUSED"` | 최종 판정 |
| `confidence` | `float` (0.0~1.0) | 신뢰도 점수 |
| `summary` | `string` | 분석 요약 (한글) |
| `rationale` | `string[]` | 판정 근거 리스트 |
| `citations` | [`Citation[]`](#citation) | 참고 자료 목록 |
| `counter_evidence` | `object[]` | 반대 증거 (있을 경우) |
| `limitations` | `string[]` | 분석의 한계점 |
| `recommended_next_steps` | `string[]` | 추가 확인 권장사항 |
| `risk_flags` | `string[]` | 위험 플래그 (`LOW_EVIDENCE`, `PIPELINE_CRASH` 등) |
| `model_info` | [`ModelInfo`](#modelinfo) | 사용된 모델 정보 |
| `latency_ms` | `int` | 분석 소요 시간 (밀리초) |
| `created_at` | `string` (ISO 8601) | 분석 생성 시각 |

> **주의**: `include_full_outputs=false`일 때 `stage_logs`, `stage_outputs`, `stage_full_outputs`는 빈 배열/객체로 반환됩니다.

**Flutter 예시**:
```dart
class TruthCheckResponse {
  final String analysisId;
  final String label;
  final double confidence;
  final String summary;
  final List<String> rationale;
  final List<Citation> citations;
  final List<String> riskFlags;
  final int latencyMs;
  final String createdAt;

  TruthCheckResponse.fromJson(Map<String, dynamic> json)
      : analysisId = json['analysis_id'],
        label = json['label'],
        confidence = json['confidence'].toDouble(),
        summary = json['summary'],
        rationale = List<String>.from(json['rationale'] ?? []),
        citations = (json['citations'] as List)
            .map((c) => Citation.fromJson(c))
            .toList(),
        riskFlags = List<String>.from(json['risk_flags'] ?? []),
        latencyMs = json['latency_ms'],
        createdAt = json['created_at'];
}
```

---

### Citation

| 필드 | 타입 | 설명 |
|------|------|------|
| `source_type` | `"WIKIPEDIA" \| "NEWS" \| "WEB_URL"` | 출처 유형 |
| `title` | `string` | 제목 |
| `url` | `string?` | URL (있을 경우) |
| `quote` | `string?` | 인용문 (최대 500자) |
| `relevance` | `float?` (0.0~1.0) | 관련도 점수 |

**Flutter 예시**:
```dart
class Citation {
  final String sourceType;
  final String title;
  final String? url;
  final String? quote;
  final double? relevance;

  Citation.fromJson(Map<String, dynamic> json)
      : sourceType = json['source_type'],
        title = json['title'],
        url = json['url'],
        quote = json['quote'],
        relevance = json['relevance']?.toDouble();
}
```

---

### ModelInfo

| 필드 | 타입 | 설명 |
|------|------|------|
| `provider` | `string` | 모델 제공자 (`"local"`, `"openai"` 등) |
| `model` | `string` | 모델 이름 |
| `version` | `string` | 버전 |

---

## 에러 처리

### HTTP 상태 코드

| 코드 | 의미 | 처리 방법 |
|------|------|-----------|
| `200` | 성공 | 정상 처리 |
| `400` | 잘못된 요청 | 요청 파라미터 확인 |
| `500` | 서버 오류 | 재시도 또는 사용자에게 안내 |
| `503` | 서비스 불가 | 잠시 후 재시도 |

### 스트리밍 에러 이벤트

```json
{
  "event": "error",
  "data": {
    "code": "TIMEOUT" | "PARSING_ERROR" | "PIPELINE_ERROR",
    "stage": "stage03_wiki",
    "message": "상세 에러 메시지 (개발자용)",
    "display_message": "사용자에게 표시할 메시지"
  }
}
```

**Flutter 처리 예시**:
```dart
if (event['event'] == 'error') {
  final errorData = event['data'];
  final code = errorData['code'];
  
  switch (code) {
    case 'TIMEOUT':
      showSnackBar('네트워크가 불안정합니다. 다시 시도해주세요.');
      break;
    case 'PARSING_ERROR':
      showSnackBar('분석 중 오류가 발생했습니다.');
      break;
    default:
      showSnackBar(errorData['display_message']);
  }
}
```

---

## Flutter 통합 예제

### 1. HTTP 클라이언트 설정

```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

class OLaLaApiClient {
  static const String baseUrl = 'http://localhost:8000';
  
  Future<TruthCheckResponse> checkTruth(TruthCheckRequest request) async {
    final response = await http.post(
      Uri.parse('$baseUrl/truth/check'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(request.toJson()),
    );
    
    if (response.statusCode == 200) {
      return TruthCheckResponse.fromJson(jsonDecode(response.body));
    } else {
      throw Exception('Failed to check truth: ${response.statusCode}');
    }
  }
}
```

### 2. SSE 스트리밍 (권장)

```dart
import 'package:http/http.dart' as http;
import 'dart:convert';

Stream<Map<String, dynamic>> checkTruthStream(TruthCheckRequest request) async* {
  final client = http.Client();
  
  try {
    final streamRequest = http.Request(
      'POST',
      Uri.parse('$baseUrl/api/truth/check/stream'),
    );
    streamRequest.headers['Content-Type'] = 'application/json';
    streamRequest.body = jsonEncode(request.toJson());
    
    final response = await client.send(streamRequest);
    
    await for (var chunk in response.stream.transform(utf8.decoder)) {
      for (var line in chunk.split('\n')) {
        if (line.trim().isEmpty) continue;
        
        try {
          final event = jsonDecode(line);
          yield event;
          
          if (event['event'] == 'complete' || event['event'] == 'error') {
            break;
          }
        } catch (e) {
          print('Failed to parse event: $line');
        }
      }
    }
  } finally {
    client.close();
  }
}
```

### 3. UI 통합 예시

```dart
class TruthCheckScreen extends StatefulWidget {
  @override
  _TruthCheckScreenState createState() => _TruthCheckScreenState();
}

class _TruthCheckScreenState extends State<TruthCheckScreen> {
  String _currentStage = '대기 중';
  TruthCheckResponse? _result;
  
  void _startAnalysis(String url) {
    final request = TruthCheckRequest(
      inputType: 'url',
      inputPayload: url,
      language: 'ko',
      includeFullOutputs: false,
    );
    
    checkTruthStream(request).listen(
      (event) {
        if (event['event'] == 'stage_complete') {
          setState(() {
            _currentStage = _getStageDisplayName(event['stage']);
          });
        } else if (event['event'] == 'complete') {
          setState(() {
            _result = TruthCheckResponse.fromJson(event['data']);
            _currentStage = '완료';
          });
        } else if (event['event'] == 'error') {
          _showError(event['data']['display_message']);
        }
      },
      onError: (error) {
        _showError('분석 중 오류가 발생했습니다.');
      },
    );
  }
  
  String _getStageDisplayName(String stage) {
    const stageNames = {
      'stage01_normalize': '주장 분석 중...',
      'stage02_querygen': '검색 쿼리 생성 중...',
      'stage03_merge': '증거 수집 중...',
      'stage04_score': '증거 평가 중...',
      'stage05_topk': '핵심 증거 선별 중...',
      'stage06_verify_support': '지지 증거 검증 중...',
      'stage07_verify_skeptic': '반대 증거 검증 중...',
      'stage08_aggregate': '결과 종합 중...',
      'stage09_judge': '최종 판정 중...',
    };
    return stageNames[stage] ?? '분석 중...';
  }
  
  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Column(
        children: [
          if (_currentStage != '완료')
            LinearProgressIndicator(),
          Text(_currentStage),
          if (_result != null)
            _buildResultCard(_result!),
        ],
      ),
    );
  }
  
  Widget _buildResultCard(TruthCheckResponse result) {
    return Card(
      child: Column(
        children: [
          Text('판정: ${result.label}'),
          Text('신뢰도: ${(result.confidence * 100).toStringAsFixed(1)}%'),
          Text(result.summary),
          ...result.citations.map((c) => ListTile(
            title: Text(c.title),
            subtitle: Text(c.quote ?? ''),
          )),
        ],
      ),
    );
  }
}
```

---

## 성능 최적화 팁

### 1. 모바일 대역폭 절약
```dart
// ✅ 권장: 디버그 데이터 제외
TruthCheckRequest(
  inputPayload: url,
  includeFullOutputs: false,  // 응답 크기 약 60% 감소
)

// ❌ 비권장: 전체 데이터 포함
TruthCheckRequest(
  inputPayload: url,
  includeFullOutputs: true,  // 개발/디버깅 시에만 사용
)
```

### 2. 타임아웃 설정
```dart
final response = await http.post(
  uri,
  headers: headers,
  body: body,
).timeout(
  Duration(seconds: 60),  // 분석은 30-60초 소요
  onTimeout: () => throw TimeoutException('분석 시간 초과'),
);
```

### 3. 캐싱 전략
```dart
// 동일 URL에 대한 중복 요청 방지
final cachedResult = await _cache.get(url);
if (cachedResult != null && 
    DateTime.now().difference(cachedResult.createdAt) < Duration(hours: 1)) {
  return cachedResult;
}
```

---

## 문의 및 지원

- **이슈 트래킹**: GitHub Issues
- **API 변경사항**: [CHANGELOG.md](./CHANGELOG.md)
- **백엔드 팀 연락처**: backend-team@olala.com
