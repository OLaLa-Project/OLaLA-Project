import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:intl/intl.dart';

import '../models/daily_issue.dart';

/// 채팅 화면 상단의 이슈 정보 헤더
class IssueHeaderCard extends StatelessWidget {
  final DailyIssue issue;
  final VoidCallback? onTap;

  const IssueHeaderCard({super.key, required this.issue, this.onTap});

  static const Color _primary = Color(0xFF4683F6);
  static const Color _primarySoft = Color(0xFFE9F3FF);
  static const Color _textPrimary = Color(0xFF1F1F1F);
  static const Color _textSecondary = Color(0xFF5F6570);
  static const Color _textTertiary = Color(0xFF9AA1AD);
  static const Color _border = Color(0xFFE6E9EF);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    final card = Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: isDark ? theme.colorScheme.surface : Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isDark ? theme.colorScheme.outlineVariant : _border,
          width: 1,
        ),
        boxShadow: isDark
            ? const []
            : [
                BoxShadow(
                  color: Colors.black.withOpacity(0.04),
                  blurRadius: 10,
                  offset: const Offset(0, 3),
                ),
              ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 카테고리 + 참여자 수
          Row(
            children: [
              // 카테고리 뱃지
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 10,
                  vertical: 4,
                ),
                decoration: BoxDecoration(
                  color: _primarySoft,
                  borderRadius: BorderRadius.circular(6),
                ),
                child: Text(
                  issue.category,
                  style: const TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w700,
                    color: _primary,
                  ),
                ),
              ),
              const Spacer(),
              // 참여자 수
              Icon(
                PhosphorIconsRegular.users,
                size: 16,
                color: isDark
                    ? theme.colorScheme.onSurfaceVariant
                    : _textSecondary,
              ),
              const SizedBox(width: 4),
              Text(
                '${issue.participantCount}명 참여 중',
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w600,
                  color: isDark
                      ? theme.colorScheme.onSurfaceVariant
                      : _textSecondary,
                ),
              ),
            ],
          ),
          const SizedBox(height: 12),
          // 제목
          Text(
            issue.title,
            style: TextStyle(
              fontSize: 18,
              fontWeight: FontWeight.w700,
              color: isDark ? theme.colorScheme.onSurface : _textPrimary,
              height: 1.4,
            ),
          ),
          const SizedBox(height: 8),
          // 요약
          Text(
            issue.summary,
            style: TextStyle(
              fontSize: 14,
              color: isDark
                  ? theme.colorScheme.onSurfaceVariant
                  : _textSecondary,
              height: 1.5,
            ),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Text(
                _formatPublishedDate(issue.publishedAt),
                style: TextStyle(
                  fontSize: 12,
                  fontWeight: FontWeight.w500,
                  color: isDark ? theme.colorScheme.outline : _textTertiary,
                ),
              ),
              const Spacer(),
              if (onTap != null)
                Row(
                  children: const [
                    Text(
                      '전체 기사 보기',
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w700,
                        color: _primary,
                      ),
                    ),
                    SizedBox(width: 4),
                    Icon(
                      PhosphorIconsRegular.caretRight,
                      size: 14,
                      color: _primary,
                    ),
                  ],
                ),
            ],
          ),
        ],
      ),
    );

    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 8),
      child: onTap == null
          ? card
          : Material(
              color: Colors.transparent,
              borderRadius: BorderRadius.circular(16),
              child: InkWell(
                borderRadius: BorderRadius.circular(16),
                onTap: onTap,
                child: card,
              ),
            ),
    );
  }

  String _formatPublishedDate(DateTime publishedAt) {
    final now = DateTime.now();
    final diff = now.difference(publishedAt);

    if (diff.inMinutes < 1) {
      return '방금 전 발행';
    } else if (diff.inMinutes < 60) {
      return '${diff.inMinutes}분 전 발행';
    } else if (diff.inHours < 24) {
      return '${diff.inHours}시간 전 발행';
    } else if (diff.inDays < 7) {
      return '${diff.inDays}일 전 발행';
    } else {
      return '${DateFormat('yyyy년 MM월 dd일').format(publishedAt)} 발행';
    }
  }
}
