import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import 'package:shimmer/shimmer.dart';
import 'package:intl/intl.dart';

import '../../issue_chat/models/daily_issue.dart';
import '../../issue_chat/repository/api_issue_repository.dart';
import '../../issue_chat/repository/issue_repository.dart';
import '../../issue_chat/issue_chat_screen.dart';
import '../../../shared/network/api_endpoints.dart';

/// 오늘의 이슈 배너 위젯
class IssueBanner extends StatefulWidget {
  const IssueBanner({super.key});

  @override
  State<IssueBanner> createState() => _IssueBannerState();
}

class _IssueBannerState extends State<IssueBanner> {
  final IssueRepository _repository =
      ApiIssueRepository(baseUrl: ApiEndpoints.apiBase);
  DailyIssue? _issue;
  bool _isLoading = true;

  @override
  void initState() {
    super.initState();
    _loadIssue();
  }

  Future<void> _loadIssue() async {
    setState(() {
      _isLoading = true;
    });

    try {
      final issue = await _repository.getTodayIssue();
      if (mounted) {
        setState(() {
          _issue = issue ?? _fallbackIssue();
          _isLoading = false;
        });
      }
    } catch (e) {
      if (mounted) {
        setState(() {
          _issue = _fallbackIssue();
          _isLoading = false;
        });
      }
    }
  }

  void _onTap() {
    final issue = _issue ?? _fallbackIssue();
    Get.to(() => IssueChatScreen(issue: issue));
  }

  @override
  Widget build(BuildContext context) {
    if (_isLoading) {
      return _buildLoadingBanner();
    }

    final issue = _issue ?? _fallbackIssue();
    return _buildIssueBanner(issue);
  }

  /// 로딩 상태 배너 (Shimmer 효과)
  Widget _buildLoadingBanner() {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final baseColor = isDark ? Colors.grey[800]! : Colors.grey[300]!;
    final highlightColor = isDark ? Colors.grey[700]! : Colors.grey[100]!;

    return Container(
      height: 100,
      decoration: BoxDecoration(
        color: isDark ? theme.colorScheme.surface : Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark
              ? theme.colorScheme.outlineVariant.withOpacity(0.6)
              : Colors.black.withOpacity(0.06),
          width: 1,
        ),
      ),
      child: Shimmer.fromColors(
        baseColor: baseColor,
        highlightColor: highlightColor,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            children: [
              // 아이콘 영역
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: isDark ? theme.colorScheme.surface : Colors.white,
                  borderRadius: BorderRadius.circular(8),
                ),
              ),
              const SizedBox(width: 12),
              // 텍스트 영역
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisAlignment: MainAxisAlignment.center,
                  children: [
                    Container(
                      height: 12,
                      width: 80,
                      decoration: BoxDecoration(
                        color: isDark ? theme.colorScheme.surface : Colors.white,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                    const SizedBox(height: 8),
                    Container(
                      height: 16,
                      decoration: BoxDecoration(
                        color: isDark ? theme.colorScheme.surface : Colors.white,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                    const SizedBox(height: 6),
                    Container(
                      height: 12,
                      width: 120,
                      decoration: BoxDecoration(
                        color: isDark ? theme.colorScheme.surface : Colors.white,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              // 화살표 영역
              Container(
                width: 24,
                height: 24,
                decoration: BoxDecoration(
                  color: isDark ? theme.colorScheme.surface : Colors.white,
                  shape: BoxShape.circle,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  /// 이슈 배너
  Widget _buildIssueBanner(DailyIssue issue) {
    final timeAgo = _formatTimeAgo(issue.publishedAt);
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    const brand = Color(0xFF4683F6);

    return Container(
      height: 100,
      decoration: BoxDecoration(
        color: isDark ? theme.colorScheme.surface : Colors.white,
        borderRadius: BorderRadius.circular(12),
        border: Border.all(
          color: isDark
              ? theme.colorScheme.outlineVariant.withOpacity(0.6)
              : Colors.black.withOpacity(0.06),
          width: 1,
        ),
        boxShadow: isDark
            ? const []
            : [
                BoxShadow(
                  color: Colors.black.withOpacity(0.04),
                  blurRadius: 8,
                  offset: const Offset(0, 2),
                ),
              ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: _onTap,
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              children: [
                // 왼쪽: 카테고리 아이콘
                Container(
                  width: 44,
                  height: 44,
                  decoration: BoxDecoration(
                    color: brand.withOpacity(isDark ? 0.2 : 0.1),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: const Icon(
                    PhosphorIconsRegular.chatCircle,
                    size: 24,
                    color: brand,
                  ),
                ),
                const SizedBox(width: 12),
                // 중앙: 제목 및 정보
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      // 카테고리 + 시간
                      Row(
                        children: [
                          Container(
                            padding: const EdgeInsets.symmetric(
                              horizontal: 8,
                              vertical: 2,
                            ),
                            decoration: BoxDecoration(
                              color: isDark
                                  ? brand.withOpacity(0.2)
                                  : const Color(0xFFE9F3FF),
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Text(
                              issue.category,
                              style: const TextStyle(
                                fontSize: 11,
                                fontWeight: FontWeight.w700,
                                color: brand,
                              ),
                            ),
                          ),
                          const SizedBox(width: 8),
                          Text(
                            timeAgo,
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w500,
                              color: isDark
                                  ? theme.colorScheme.onSurfaceVariant
                                  : Colors.grey[500],
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 6),
                      // 제목
                      Text(
                        issue.title,
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w700,
                          color: isDark
                              ? theme.colorScheme.onSurface
                              : const Color(0xFF1F1F1F),
                          height: 1.3,
                        ),
                      ),
                      const SizedBox(height: 4),
                      // 참여자 수
                      Row(
                        children: [
                          Icon(
                            PhosphorIconsRegular.users,
                            size: 14,
                            color: isDark
                                ? theme.colorScheme.onSurfaceVariant
                                : Colors.grey[600],
                          ),
                          const SizedBox(width: 4),
                          Text(
                            '${issue.participantCount}명 참여 중',
                            style: TextStyle(
                              fontSize: 11,
                              fontWeight: FontWeight.w500,
                              color: isDark
                                  ? theme.colorScheme.onSurfaceVariant
                                  : Colors.grey[600],
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
                const SizedBox(width: 8),
                // 오른쪽: 화살표 아이콘
                Icon(
                  PhosphorIconsRegular.caretRight,
                  size: 20,
                  color: isDark ? theme.colorScheme.outline : Colors.grey[400],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }

  String _formatTimeAgo(DateTime publishedAt) {
    final now = DateTime.now();
    final difference = now.difference(publishedAt);

    if (difference.inMinutes < 1) {
      return '방금 전';
    } else if (difference.inMinutes < 60) {
      return '${difference.inMinutes}분 전';
    } else if (difference.inHours < 24) {
      return '${difference.inHours}시간 전';
    } else {
      return DateFormat('MM월 dd일').format(publishedAt);
    }
  }

  DailyIssue _fallbackIssue() {
    final now = DateTime.now();
    final dateKey = DateFormat('yyyyMMdd').format(now);

    return DailyIssue(
      id: 'issue_fallback_$dateKey',
      title: '오늘의 이슈 토론에 참여해보세요',
      summary: '앱 사용자들과 실시간으로 의견을 나눌 수 있어요.',
      content: '',
      category: '오늘의 이슈',
      participantCount: 0,
      publishedAt: now,
    );
  }
}
