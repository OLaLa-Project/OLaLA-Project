import 'package:flutter_test/flutter_test.dart';
import 'package:olala_frontend/features/issue_chat/services/chat_join_link.dart';

void main() {
  group('ChatJoinLink', () {
    test('buildWebChatLink creates /web-chat URL with query', () {
      final result = ChatJoinLink.buildWebChatLink(
        baseUrl: Uri.parse('https://demo.ngrok-free.app'),
        issueId: 'issue_20260209',
        title: '오늘의 이슈',
      );

      final uri = Uri.parse(result);
      expect(uri.scheme, 'https');
      expect(uri.host, 'demo.ngrok-free.app');
      expect(uri.path, '/web-chat');
      expect(uri.queryParameters['issueId'], 'issue_20260209');
      expect(uri.queryParameters['title'], '오늘의 이슈');
    });

    test('extractIssueId supports web chat link', () {
      final issueId = ChatJoinLink.extractIssueId(
        'https://demo.ngrok-free.app/web-chat?issueId=issue_20260209',
      );
      expect(issueId, 'issue_20260209');
    });

    test('isPublicWebBaseUrl rejects local/private hosts', () {
      expect(
        ChatJoinLink.isPublicWebBaseUrl(Uri.parse('http://localhost:8000')),
        isFalse,
      );
      expect(
        ChatJoinLink.isPublicWebBaseUrl(Uri.parse('http://127.0.0.1:8000')),
        isFalse,
      );
      expect(
        ChatJoinLink.isPublicWebBaseUrl(Uri.parse('http://10.0.2.2:8000')),
        isFalse,
      );
      expect(
        ChatJoinLink.isPublicWebBaseUrl(Uri.parse('http://192.168.0.20:8000')),
        isFalse,
      );
      expect(
        ChatJoinLink.isPublicWebBaseUrl(Uri.parse('http://172.16.1.20:8000')),
        isFalse,
      );
      expect(
        ChatJoinLink.isPublicWebBaseUrl(Uri.parse('https://a.example.com')),
        isTrue,
      );
    });
  });
}
