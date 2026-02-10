import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;

import '../models/verification_request.dart';
import '../models/verification_result.dart';
import 'verify_endpoints.dart';
import 'verify_repository.dart';

class ApiVerifyRepository implements VerifyRepository {
  final String baseUrl;
  final http.Client _httpClient;
  final Duration _requestTimeout;
  final Map<String, String> Function()? _headersBuilder;

  ApiVerifyRepository({
    required this.baseUrl,
    http.Client? httpClient,
    Duration requestTimeout = const Duration(seconds: 20),
    Map<String, String> Function()? headersBuilder,
  }) : _httpClient = httpClient ?? http.Client(),
       _requestTimeout = requestTimeout,
       _headersBuilder = headersBuilder;

  @override
  Future<VerificationResult> verify(
    VerificationRequest request, {
    void Function(int step, String message)? onProgress,
  }) async {
    final trimmedInput = request.input.trim();
    if (trimmedInput.isEmpty) {
      throw const FormatException('검증 입력값이 비어 있습니다.');
    }

    onProgress?.call(0, '주장을 분석하고 있어요');
    await Future.delayed(const Duration(milliseconds: 200));
    onProgress?.call(1, '관련 근거를 찾고 있어요');

    final uri = _buildUri(VerifyEndpoints.analyze);
    final body = jsonEncode({
      'input': trimmedInput,
      'mode': _inferMode(trimmedInput),
      'timestamp': request.timestamp.toIso8601String(),
    });

    try {
      final response = await _httpClient
          .post(uri, headers: _buildHeaders(), body: body)
          .timeout(_requestTimeout);

      _throwIfNotSuccess(response, endpoint: uri.toString());

      final decoded = _decodeJson(response);
      final payload = _unwrapDataMap(decoded);

      onProgress?.call(2, '최종 판단을 만들고 있어요');
      await Future.delayed(const Duration(milliseconds: 180));

      return VerificationResult.fromJson(payload);
    } on TimeoutException catch (e) {
      throw Exception('요청 시간이 초과되었습니다. ${e.message ?? ''}'.trim());
    } on SocketException catch (e) {
      throw Exception('네트워크 연결을 확인해주세요. ${e.message}'.trim());
    } on FormatException catch (e) {
      throw Exception('서버 응답 파싱에 실패했습니다. ${e.message}'.trim());
    } catch (e) {
      rethrow;
    }
  }

  String _inferMode(String input) {
    final lowered = input.toLowerCase();
    if (lowered.startsWith('http://') || lowered.startsWith('https://')) {
      return 'url';
    }
    return 'text';
  }

  Map<String, String> _buildHeaders() {
    return {
      'Accept': 'application/json',
      'Content-Type': 'application/json',
      ...?_headersBuilder?.call(),
    };
  }

  void _throwIfNotSuccess(http.Response response, {required String endpoint}) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return;
    }
    throw Exception('요청 실패: $endpoint (${response.statusCode})');
  }

  dynamic _decodeJson(http.Response response) {
    if (response.bodyBytes.isEmpty) {
      throw const FormatException('Empty response');
    }
    String decodedText;
    try {
      decodedText = utf8.decode(response.bodyBytes);
    } on FormatException {
      decodedText = response.body;
    }
    return jsonDecode(decodedText);
  }

  Map<String, dynamic> _unwrapDataMap(dynamic decoded) {
    if (decoded is Map<String, dynamic>) {
      final data = decoded['data'];
      if (data is Map<String, dynamic>) {
        return data;
      }
      return decoded;
    }
    throw const FormatException('Invalid response payload');
  }

  Uri _buildUri(String path) {
    final normalizedBase = baseUrl.endsWith('/')
        ? baseUrl.substring(0, baseUrl.length - 1)
        : baseUrl;
    return Uri.parse('$normalizedBase$path');
  }
}
