import 'package:flutter/material.dart';

import '../../shared/network/api_endpoints.dart';
import 'issue_chat_screen.dart';
import 'models/daily_issue.dart';
import 'repository/api_issue_repository.dart';
import 'repository/issue_repository.dart';

/// 웹 QR 링크 진입점 (/web-chat?issueId=...)
/// 링크 파라미터를 해석한 뒤 기존 Flutter 채팅 화면을 그대로 렌더링한다.
class WebChatEntryScreen extends StatefulWidget {
  const WebChatEntryScreen({super.key});

  @override
  State<WebChatEntryScreen> createState() => _WebChatEntryScreenState();
}

class _WebChatEntryScreenState extends State<WebChatEntryScreen> {
  final IssueRepository _repository =
      ApiIssueRepository(baseUrl: ApiEndpoints.apiBase);

  late final String? _issueId;
  late final String? _titleFromQuery;
  late final Future<DailyIssue?> _issueFuture;

  @override
  void initState() {
    super.initState();
    final uri = Uri.base;
    _issueId = _readIssueId(uri);
    _titleFromQuery = _readTitle(uri);
    _issueFuture = _loadIssue();
  }

  Future<DailyIssue?> _loadIssue() async {
    final issueId = _issueId;
    if (issueId == null) return null;

    try {
      final fetched = await _repository.getIssueById(issueId);
      if (fetched != null) {
        return fetched.copyWith(
          id: fetched.id.trim().isNotEmpty ? fetched.id : issueId,
          title: fetched.title.trim().isNotEmpty
              ? fetched.title
              : (_titleFromQuery ?? '오늘의 이슈 채팅'),
          summary: fetched.summary.trim().isNotEmpty
              ? fetched.summary
              : '실시간 채팅에 참여해보세요.',
          category: fetched.category.trim().isNotEmpty
              ? fetched.category
              : '오늘의 이슈',
        );
      }
    } catch (_) {
      // 링크 진입은 실패 대신 fallback 이슈로 채팅 화면을 연다.
    }

    return _fallbackIssue(issueId, _titleFromQuery);
  }

  @override
  Widget build(BuildContext context) {
    return FutureBuilder<DailyIssue?>(
      future: _issueFuture,
      builder: (context, snapshot) {
        if (snapshot.connectionState != ConnectionState.done) {
          return const _WebChatLoadingView();
        }

        final issue = snapshot.data;
        if (issue == null) {
          return const _WebChatInvalidLinkView();
        }

        return IssueChatScreen(issue: issue);
      },
    );
  }

  String? _readIssueId(Uri uri) {
    final issueId = uri.queryParameters['issueId']?.trim();
    if (issueId == null || issueId.isEmpty) return null;
    return issueId;
  }

  String? _readTitle(Uri uri) {
    final title = uri.queryParameters['title']?.trim();
    if (title == null || title.isEmpty) return null;
    return title;
  }

  DailyIssue _fallbackIssue(String issueId, String? titleFromQuery) {
    final headline = titleFromQuery ?? '오늘의 이슈 채팅';

    return DailyIssue(
      id: issueId,
      title: headline,
      summary: '실시간 채팅에 참여해보세요.',
      content: '',
      category: '오늘의 이슈',
      participantCount: 0,
      publishedAt: DateTime.now(),
    );
  }
}

class _WebChatLoadingView extends StatelessWidget {
  const _WebChatLoadingView();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: isDark
          ? theme.colorScheme.surfaceContainerHighest
          : const Color(0xFFF7F8FA),
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircularProgressIndicator(
              color: isDark ? theme.colorScheme.primary : const Color(0xFF4683F6),
            ),
            const SizedBox(height: 14),
            Text(
              '채팅방에 접속 중입니다...',
              style: TextStyle(
                fontSize: 14,
                fontWeight: FontWeight.w600,
                color: isDark
                    ? theme.colorScheme.onSurface
                    : const Color(0xFF1F1F1F),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _WebChatInvalidLinkView extends StatelessWidget {
  const _WebChatInvalidLinkView();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: isDark
          ? theme.colorScheme.surfaceContainerHighest
          : const Color(0xFFF7F8FA),
      body: Center(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                Icons.link_off_rounded,
                size: 44,
                color: isDark
                    ? theme.colorScheme.onSurfaceVariant
                    : const Color(0xFF7A7A7A),
              ),
              const SizedBox(height: 12),
              Text(
                '유효하지 않은 채팅 링크입니다.',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: isDark
                      ? theme.colorScheme.onSurface
                      : const Color(0xFF1F1F1F),
                ),
              ),
              const SizedBox(height: 6),
              Text(
                'QR 코드를 다시 스캔해 주세요.',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 13,
                  color: isDark
                      ? theme.colorScheme.onSurfaceVariant
                      : const Color(0xFF5F6570),
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
