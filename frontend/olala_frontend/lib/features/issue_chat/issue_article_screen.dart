import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:intl/intl.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import 'models/daily_issue.dart';

/// 이슈 전체 기사 화면
class IssueArticleScreen extends StatelessWidget {
  final DailyIssue issue;

  const IssueArticleScreen({super.key, required this.issue});

  static const Color _background = Color(0xFFF7F8FA);
  static const Color _textPrimary = Color(0xFF1F1F1F);
  static const Color _textSecondary = Color(0xFF5F6570);
  static const Color _textTertiary = Color(0xFF9AA1AD);
  static const Color _primary = Color(0xFF4683F6);
  static const Color _border = Color(0xFFE6E9EF);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: isDark
          ? theme.colorScheme.surfaceContainerHighest
          : _background,
      appBar: AppBar(
        backgroundColor: isDark ? theme.colorScheme.surface : Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: Icon(
            PhosphorIconsRegular.caretLeft,
            size: 28,
            color: isDark ? theme.colorScheme.onSurface : _textPrimary,
          ),
          onPressed: () => Get.back(),
        ),
        title: Text(
          '전체 기사',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w700,
            color: isDark ? theme.colorScheme.onSurface : _textPrimary,
          ),
        ),
        centerTitle: true,
        bottom: PreferredSize(
          preferredSize: Size.fromHeight(1),
          child: Divider(
            height: 1,
            thickness: 1,
            color: isDark ? theme.colorScheme.outlineVariant : _border,
          ),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildMetaRow(context, isDark),
            const SizedBox(height: 12),
            Text(
              issue.title,
              style: TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w800,
                color: isDark ? theme.colorScheme.onSurface : _textPrimary,
                height: 1.4,
              ),
            ),
            const SizedBox(height: 10),
            Text(
              issue.summary,
              style: TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w500,
                color: isDark
                    ? theme.colorScheme.onSurfaceVariant
                    : _textSecondary,
                height: 1.55,
              ),
            ),
            const SizedBox(height: 18),
            _buildDivider(context, isDark),
            const SizedBox(height: 18),
            SelectableText(
              issue.content.isNotEmpty ? issue.content : '전체 기사 본문이 준비 중입니다.',
              style: TextStyle(
                fontSize: 15,
                color: isDark ? theme.colorScheme.onSurface : _textPrimary,
                height: 1.7,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMetaRow(BuildContext context, bool isDark) {
    final theme = Theme.of(context);

    return Row(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: _primary.withValues(alpha: 0.12),
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
        Icon(
          PhosphorIconsRegular.users,
          size: 16,
          color: isDark ? theme.colorScheme.onSurfaceVariant : _textSecondary,
        ),
        const SizedBox(width: 4),
        Text(
          '${issue.participantCount}명 참여 중',
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: isDark ? theme.colorScheme.onSurfaceVariant : _textSecondary,
          ),
        ),
        const SizedBox(width: 12),
        Text(
          DateFormat('yyyy.MM.dd').format(issue.publishedAt),
          style: TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w500,
            color: isDark ? theme.colorScheme.outline : _textTertiary,
          ),
        ),
      ],
    );
  }

  Widget _buildDivider(BuildContext context, bool isDark) {
    final theme = Theme.of(context);

    return Container(
      height: 1,
      decoration: BoxDecoration(
        color: isDark ? theme.colorScheme.outlineVariant : _border,
        borderRadius: BorderRadius.circular(10),
      ),
    );
  }
}
