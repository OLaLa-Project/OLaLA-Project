import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:async';
import 'package:flutter/foundation.dart';
import '../../app/env.dart';

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

class Citation {
  final String sourceType;
  final String title;
  final String? url;
  final String? quote;
  final double? relevance;

  Citation.fromJson(Map<String, dynamic> json)
      : sourceType = json['source_type'] ?? 'UNKNOWN',
        title = json['title'] ?? '',
        url = json['url'],
        quote = json['quote'],
        relevance = json['relevance']?.toDouble();
}

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
      : analysisId = json['analysis_id'] ?? '',
        label = json['label'] ?? 'UNKNOWN',
        confidence = (json['confidence'] ?? 0.0).toDouble(),
        summary = json['summary'] ?? '',
        rationale = List<String>.from(json['rationale'] ?? []),
        citations = (json['citations'] as List? ?? [])
            .map((c) => Citation.fromJson(c))
            .toList(),
        riskFlags = List<String>.from(json['risk_flags'] ?? []),
        latencyMs = json['latency_ms'] ?? 0,
        createdAt = json['created_at'] ?? '';
}

class OLaLaApiClient {
  final http.Client _client = http.Client();

  /// 스트리밍 분석 요청 (SSE)
  Stream<Map<String, dynamic>> checkTruthStream(TruthCheckRequest request) async* {
    final uri = Uri.parse('${Env.apiBaseUrl}/api/truth/check/stream');
    
    try {
      final streamRequest = http.Request('POST', uri);
      streamRequest.headers['Content-Type'] = 'application/json';
      streamRequest.headers['Accept'] = 'text/event-stream';
      streamRequest.body = jsonEncode(request.toJson());

      if (Env.enableApiLog) {
        debugPrint('Available: POST $uri');
        debugPrint('Body: ${streamRequest.body}');
      }

      final response = await _client.send(streamRequest);

      await for (var chunk in response.stream.transform(utf8.decoder)) {
        // SSE 이벤트는 "data: ..." 형식이거나, 그냥 JSON 객체가 올 수도 있음 (서버 구현에 따라 다름)
        // API SPEC에 따르면 JSON 객체가 줄바꿈으로 옴.
        
        if (chunk.trim().isEmpty) continue;
        
        // 여러 줄이 한 번에 올 수 있으므로 라인별 처리
        final lines = chunk.split('\n');
        for (var line in lines) {
           if (line.trim().isEmpty) continue;
           
           try {
             // SSE 표준 포맷(data: {})인지, 그냥 Raw JSON인지 확인 필요.
             // API SPEC 예시는 {"event": ...} 형태의 Raw JSON Stream 처럼 보임.
             // 하지만 보통 SSE는 prefix가 있음.
             // 여기서는 SPEC에 적힌대로 JSON 파싱 시도.
             
             // 1. 순수 JSON 파싱 시도
             try {
               final event = jsonDecode(line);
               yield event;
             } catch (e) {
               // 2. data: Prefix 제거 시도 (표준 SSE)
               if (line.startsWith('data:')) {
                 final jsonStr = line.substring(5).trim();
                 if (jsonStr.isNotEmpty) {
                    final event = jsonDecode(jsonStr);
                    yield event;
                 }
               }
             }

           } catch (e) {
             debugPrint('Failed to parse event: $line, error: $e');
           }
        }
      }
    } catch (e) {
      debugPrint('Stream Error: $e');
      yield {
        'event': 'error', 
        'data': {
          'code': 'CONNECTION_ERROR',
          'display_message': '서버 연결에 실패했습니다. ($e)'
        }
      };
    }
  }

  void close() {
    _client.close();
  }
}
