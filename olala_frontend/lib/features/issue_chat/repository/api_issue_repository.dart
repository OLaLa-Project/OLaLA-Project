import 'package:http/http.dart' as http;
import 'dart:convert';

import '../models/daily_issue.dart';
import '../models/chat_message.dart';
import 'issue_repository.dart';
import '../../../shared/network/api_endpoints.dart';

class ApiIssueRepository implements IssueRepository {
  final String baseUrl;

  ApiIssueRepository({required this.baseUrl});

  @override
  Future<DailyIssue?> getTodayIssue() async {
    try {
      final response = await http.get(_buildUri(ApiEndpoints.todayIssue));

      if (response.statusCode == 200) {
        final json = jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
        return DailyIssue.fromJson(json);
      }
      return null;
    } catch (e) {
      print('Error fetching today issue: $e');
      return null;
    }
  }

  @override
  Future<List<ChatMessage>> getChatHistory(String issueId, {int limit = 50}) async {
    try {
      final uri = _buildUri('${ApiEndpoints.chatHistory}/$issueId')
          .replace(queryParameters: {'limit': '$limit'});
      final response = await http.get(uri);

      if (response.statusCode == 200) {
        final jsonList = jsonDecode(utf8.decode(response.bodyBytes)) as List;
        return jsonList.map((json) => ChatMessage.fromJson(json as Map<String, dynamic>)).toList();
      }
      return [];
    } catch (e) {
      print('Error fetching chat history: $e');
      return [];
    }
  }

  Uri _buildUri(String path) {
    final normalizedBase = baseUrl.endsWith('/')
        ? baseUrl.substring(0, baseUrl.length - 1)
        : baseUrl;
    return Uri.parse('$normalizedBase$path');
  }
}
