import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:olala_frontend/features/issue_chat/repository/api_issue_repository.dart';
import 'package:olala_frontend/features/issue_chat/repository/issue_repository_exception.dart';

void main() {
  group('ApiIssueRepository', () {
    test('getTodayIssue returns issue from object payload', () async {
      late Uri calledUri;
      final repo = ApiIssueRepository(
        baseUrl: 'https://example.com',
        httpClient: MockClient((request) async {
          calledUri = request.url;
          return http.Response(
            jsonEncode({
              'id': 'issue_1',
              'title': 'title',
              'summary': 'summary',
              'content': 'content',
              'category': 'politics',
              'participantCount': 12,
              'publishedAt': '2026-02-07T10:00:00.000Z',
            }),
            200,
          );
        }),
      );

      final issue = await repo.getTodayIssue();
      expect(issue, isNotNull);
      expect(issue!.id, 'issue_1');
      expect(issue.participantCount, 12);
      expect(calledUri.path, '/issues/today');
    });

    test('getTodayIssue supports wrapped data payload', () async {
      final repo = ApiIssueRepository(
        baseUrl: 'https://example.com',
        httpClient: MockClient((_) async {
          return http.Response(
            jsonEncode({
              'data': {
                'id': 'issue_2',
                'title': 'title',
                'summary': 'summary',
                'content': '',
                'category': 'social',
                'participantCount': 9,
                'publishedAt': '2026-02-07T10:00:00.000Z',
              },
            }),
            200,
          );
        }),
      );

      final issue = await repo.getTodayIssue();
      expect(issue, isNotNull);
      expect(issue!.id, 'issue_2');
    });

    test('getTodayIssue returns null on 404', () async {
      final repo = ApiIssueRepository(
        baseUrl: 'https://example.com',
        httpClient: MockClient((_) async => http.Response('', 404)),
      );

      final issue = await repo.getTodayIssue();
      expect(issue, isNull);
    });

    test('getChatHistory supports list and wrapped list payload', () async {
      var callCount = 0;
      final repo = ApiIssueRepository(
        baseUrl: 'https://example.com',
        httpClient: MockClient((request) async {
          callCount += 1;
          if (callCount == 1) {
            return http.Response(
              jsonEncode([
                {
                  'id': 'm1',
                  'userId': 'u1',
                  'username': 'a',
                  'content': 'hi',
                  'timestamp': '2026-02-07T10:00:00.000Z',
                },
              ]),
              200,
            );
          }
          expect(request.url.queryParameters['limit'], '20');
          return http.Response(
            jsonEncode({
              'data': [
                {
                  'id': 'm2',
                  'userId': 'u2',
                  'username': 'b',
                  'content': 'hello',
                  'timestamp': '2026-02-07T11:00:00.000Z',
                },
              ],
            }),
            200,
          );
        }),
      );

      final first = await repo.getChatHistory('issue_1');
      final second = await repo.getChatHistory('issue_1', limit: 20);

      expect(first, hasLength(1));
      expect(first.first.id, 'm1');
      expect(second, hasLength(1));
      expect(second.first.id, 'm2');
    });

    test(
      'getChatHistory throws IssueRepositoryException on server error',
      () async {
        final repo = ApiIssueRepository(
          baseUrl: 'https://example.com',
          httpClient: MockClient(
            (_) async => http.Response('server error', 500),
          ),
        );

        expect(
          () => repo.getChatHistory('issue_1'),
          throwsA(
            isA<IssueRepositoryException>().having(
              (e) => e.statusCode,
              'statusCode',
              500,
            ),
          ),
        );
      },
    );
  });
}
