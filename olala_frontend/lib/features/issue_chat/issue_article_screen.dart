import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:intl/intl.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import 'models/daily_issue.dart';

/// 이슈 전체 기사 화면
class IssueArticleScreen extends StatelessWidget {
  final DailyIssue issue;

  const IssueArticleScreen({
    super.key,
    required this.issue,
  });

  static const Color _background = Color(0xFFF7F8FA);
  static const Color _textPrimary = Color(0xFF1F1F1F);
  static const Color _textSecondary = Color(0xFF5F6570);
  static const Color _textTertiary = Color(0xFF9AA1AD);
  static const Color _primary = Color(0xFF4683F6);
  static const Color _border = Color(0xFFE6E9EF);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _background,
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(
            PhosphorIconsRegular.caretLeft,
            size: 28,
            color: _textPrimary,
          ),
          onPressed: () => Get.back(),
        ),
        title: const Text(
          '전체 기사',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w700,
            color: _textPrimary,
          ),
        ),
        centerTitle: true,
        bottom: const PreferredSize(
          preferredSize: Size.fromHeight(1),
          child: Divider(
            height: 1,
            thickness: 1,
            color: _border,
          ),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.fromLTRB(16, 16, 16, 28),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            _buildMetaRow(),
            const SizedBox(height: 12),
            Text(
              issue.title,
              style: const TextStyle(
                fontSize: 20,
                fontWeight: FontWeight.w800,
                color: _textPrimary,
                height: 1.4,
              ),
            ),
            const SizedBox(height: 10),
            Text(
              issue.summary,
              style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w500,
                color: _textSecondary,
                height: 1.55,
              ),
            ),
            const SizedBox(height: 18),
            _buildDivider(),
            const SizedBox(height: 18),
            SelectableText(
              issue.content.isNotEmpty ? issue.content : '전체 기사 본문이 준비 중입니다.',
              style: const TextStyle(
                fontSize: 15,
                color: _textPrimary,
                height: 1.7,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMetaRow() {
    return Row(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
          decoration: BoxDecoration(
            color: _primary.withOpacity(0.12),
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
          color: _textSecondary,
        ),
        const SizedBox(width: 4),
        Text(
          '${issue.participantCount}명 참여 중',
          style: const TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w600,
            color: _textSecondary,
          ),
        ),
        const SizedBox(width: 12),
        Text(
          DateFormat('yyyy.MM.dd').format(issue.publishedAt),
          style: const TextStyle(
            fontSize: 12,
            fontWeight: FontWeight.w500,
            color: _textTertiary,
          ),
        ),
      ],
    );
  }

  Widget _buildDivider() {
    return Container(
      height: 1,
      decoration: BoxDecoration(
        color: _border,
        borderRadius: BorderRadius.circular(10),
      ),
    );
  }
}
