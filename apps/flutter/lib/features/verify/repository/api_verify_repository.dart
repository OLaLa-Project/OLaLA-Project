import 'dart:convert';

import 'package:http/http.dart' as http;

import '../models/evidence_card.dart';
import '../models/verification_request.dart';
import '../models/verification_result.dart';
import 'verify_repository.dart';

class ApiVerifyRepository implements VerifyRepository {
  final String baseUrl;
  final VerifyRepository? fallback;
  final http.Client _client;

  ApiVerifyRepository({
    required this.baseUrl,
    this.fallback,
    http.Client? client,
  }) : _client = client ?? http.Client();

  @override
  Future<VerificationResult> verify(
    VerificationRequest request, {
    void Function(int step, String message)? onProgress,
  }) async {
    onProgress?.call(0, '주장을 분석하고 있어요');

    final uri = _buildUri('/truth/check');
    final payload = {
      'input_type': _guessInputType(request.input),
      'input_payload': request.input,
      'language': 'ko',
      'include_full_outputs': false,
    };

    onProgress?.call(1, '관련 근거를 찾고 있어요');

    try {
      final response = await _client.post(
        uri,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode(payload),
      );

      if (response.statusCode != 200) {
        throw Exception('verify api failed: ${response.statusCode}');
      }

      final json = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
      onProgress?.call(2, '최종 판단을 만들고 있어요');
      return _toVerificationResult(json);
    } catch (e) {
      if (fallback != null) {
        return fallback!.verify(request, onProgress: onProgress);
      }
      rethrow;
    }
  }

  Uri _buildUri(String path) {
    final normalizedBase = baseUrl.endsWith('/')
        ? baseUrl.substring(0, baseUrl.length - 1)
        : baseUrl;
    return Uri.parse('$normalizedBase$path');
  }

  String _guessInputType(String input) {
    final trimmed = input.trim().toLowerCase();
    if (trimmed.startsWith('http://') || trimmed.startsWith('https://')) {
      return 'url';
    }
    return 'text';
  }

  VerificationResult _toVerificationResult(Map<String, dynamic> json) {
    final label = (json['label'] ?? 'UNVERIFIED').toString().toUpperCase();
    final verdict = switch (label) {
      'TRUE' => 'true',
      'FALSE' => 'false',
      'MIXED' => 'mixed',
      _ => 'unverified',
    };

    final summary = (json['summary'] ?? '').toString();
    final headline = (json['headline'] ?? _defaultHeadline(label)).toString();
    final rationale = (json['rationale'] is List)
        ? (json['rationale'] as List)
            .map((e) => e.toString().trim())
            .where((e) => e.isNotEmpty)
            .toList()
        : <String>[];

    final evidence = (json['citations'] is List)
        ? (json['citations'] as List)
            .whereType<Map<String, dynamic>>()
            .map(
              (item) => EvidenceCard(
                title: item['title']?.toString(),
                source: item['source_type']?.toString(),
                snippet: item['quote']?.toString(),
                url: item['url']?.toString(),
                score: (item['relevance'] is num)
                    ? (item['relevance'] as num).toDouble()
                    : null,
              ),
            )
            .toList()
        : <EvidenceCard>[];

    final reason = rationale.isNotEmpty ? rationale.join('\n') : summary;

    return VerificationResult(
      verdict: verdict,
      confidence: (json['confidence'] is num)
          ? (json['confidence'] as num).toDouble()
          : 0.0,
      headline: headline,
      reason: reason,
      evidenceCards: evidence,
    );
  }

  String _defaultHeadline(String label) {
    return switch (label) {
      'TRUE' => '대체로 사실이에요',
      'FALSE' => '사실이 아닐 가능성이 높아요',
      'MIXED' => '판단이 엇갈리는 주장입니다',
      _ => '추가 검증이 필요해요',
    };
  }
}
