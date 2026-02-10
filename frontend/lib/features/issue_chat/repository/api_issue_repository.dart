import 'dart:async';
import 'package:http/http.dart' as http;
import 'dart:convert';
import 'dart:io';

import '../models/daily_issue.dart';
import '../models/chat_message.dart';
import 'issue_repository.dart';
import '../../../shared/network/api_endpoints.dart';
import 'issue_repository_exception.dart';

class ApiIssueRepository implements IssueRepository {
  final String baseUrl;
  final http.Client _httpClient;
  final Duration _requestTimeout;
  final Map<String, String> Function()? _headersBuilder;

  ApiIssueRepository({
    required this.baseUrl,
    http.Client? httpClient,
    Duration requestTimeout = const Duration(seconds: 10),
    Map<String, String> Function()? headersBuilder,
  }) : _httpClient = httpClient ?? http.Client(),
       _requestTimeout = requestTimeout,
       _headersBuilder = headersBuilder;

  @override
  Future<DailyIssue?> getTodayIssue() async {
    final uri = _buildUri(ApiEndpoints.todayIssue);

    try {
      final response = await _httpClient
          .get(uri, headers: _buildHeaders())
          .timeout(_requestTimeout);

      if (response.statusCode == 404) {
        return null;
      }
      _throwIfNotSuccess(response, endpoint: uri.toString());

      final decoded = _decodeJson(response);
      if (decoded is Map<String, dynamic>) {
        final payload = _unwrapDataMap(decoded);
        return DailyIssue.fromJson(payload);
      }
      throw const IssueRepositoryException('응답 형식이 올바르지 않습니다.');
    } on IssueRepositoryException {
      rethrow;
    } on TimeoutException catch (e) {
      throw IssueRepositoryException('요청 시간이 초과되었습니다.', cause: e);
    } on SocketException catch (e) {
      throw IssueRepositoryException('네트워크 연결을 확인해주세요.', cause: e);
    } on FormatException catch (e) {
      throw IssueRepositoryException('서버 응답 파싱에 실패했습니다.', cause: e);
    } catch (e) {
      throw IssueRepositoryException('이슈 정보를 불러오지 못했습니다.', cause: e);
    }
  }

  @override
  Future<DailyIssue?> getIssueById(String issueId) async {
    final trimmedIssueId = issueId.trim();
    if (trimmedIssueId.isEmpty) {
      throw const IssueRepositoryException('유효한 이슈 ID가 필요합니다.');
    }

    final encodedIssueId = Uri.encodeComponent(trimmedIssueId);
    final uri = _buildUri('${ApiEndpoints.issueDetail}/$encodedIssueId');

    try {
      final response = await _httpClient
          .get(uri, headers: _buildHeaders())
          .timeout(_requestTimeout);

      if (response.statusCode == 404) {
        return null;
      }
      _throwIfNotSuccess(response, endpoint: uri.toString());

      final decoded = _decodeJson(response);
      if (decoded is Map<String, dynamic>) {
        final payload = _unwrapDataMap(decoded);
        return DailyIssue.fromJson(payload);
      }
      throw const IssueRepositoryException('응답 형식이 올바르지 않습니다.');
    } on IssueRepositoryException {
      rethrow;
    } on TimeoutException catch (e) {
      throw IssueRepositoryException('요청 시간이 초과되었습니다.', cause: e);
    } on SocketException catch (e) {
      throw IssueRepositoryException('네트워크 연결을 확인해주세요.', cause: e);
    } on FormatException catch (e) {
      throw IssueRepositoryException('서버 응답 파싱에 실패했습니다.', cause: e);
    } catch (e) {
      throw IssueRepositoryException('이슈 정보를 불러오지 못했습니다.', cause: e);
    }
  }

  @override
  Future<List<ChatMessage>> getChatHistory(
    String issueId, {
    int limit = 50,
  }) async {
    final uri = _buildUri(
      '${ApiEndpoints.chatHistory}/$issueId',
    ).replace(queryParameters: {'limit': '${limit.clamp(1, 200)}'});

    try {
      final response = await _httpClient
          .get(uri, headers: _buildHeaders())
          .timeout(_requestTimeout);

      if (response.statusCode == 404) {
        return const [];
      }
      _throwIfNotSuccess(response, endpoint: uri.toString());

      final decoded = _decodeJson(response);
      if (decoded is List) {
        return decoded
            .whereType<Map<String, dynamic>>()
            .map(ChatMessage.fromJson)
            .toList();
      }
      if (decoded is Map<String, dynamic>) {
        final data = decoded['data'];
        if (data is List) {
          return data
              .whereType<Map<String, dynamic>>()
              .map(ChatMessage.fromJson)
              .toList();
        }
      }

      throw const IssueRepositoryException('채팅 히스토리 응답 형식이 올바르지 않습니다.');
    } on IssueRepositoryException {
      rethrow;
    } on TimeoutException catch (e) {
      throw IssueRepositoryException('요청 시간이 초과되었습니다.', cause: e);
    } on SocketException catch (e) {
      throw IssueRepositoryException('네트워크 연결을 확인해주세요.', cause: e);
    } on FormatException catch (e) {
      throw IssueRepositoryException('채팅 히스토리 파싱에 실패했습니다.', cause: e);
    } catch (e) {
      throw IssueRepositoryException('채팅 히스토리를 불러오지 못했습니다.', cause: e);
    }
  }

  Map<String, String> _buildHeaders() {
    return {'Accept': 'application/json', ...?_headersBuilder?.call()};
  }

  void _throwIfNotSuccess(http.Response response, {required String endpoint}) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return;
    }
    throw IssueRepositoryException(
      '요청 실패: $endpoint',
      statusCode: response.statusCode,
    );
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

  Map<String, dynamic> _unwrapDataMap(Map<String, dynamic> body) {
    final data = body['data'];
    if (data is Map<String, dynamic>) {
      return data;
    }
    return body;
  }

  Uri _buildUri(String path) {
    final normalizedBase = baseUrl.endsWith('/')
        ? baseUrl.substring(0, baseUrl.length - 1)
        : baseUrl;
    return Uri.parse('$normalizedBase$path');
  }
}
