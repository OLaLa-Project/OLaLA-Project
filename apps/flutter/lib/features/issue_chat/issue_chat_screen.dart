import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import 'models/daily_issue.dart';
import 'issue_chat_controller.dart';
import 'issue_article_screen.dart';
import 'widgets/issue_header_card.dart';
import 'widgets/chat_message_bubble.dart';
import 'widgets/chat_input_field.dart';

/// 채팅 화면
class IssueChatScreen extends StatelessWidget {
  final DailyIssue issue;

  const IssueChatScreen({super.key, required this.issue});

  static const Color _background = Color(0xFFF7F8FA);
  static const Color _textPrimary = Color(0xFF1F1F1F);
  static const Color _border = Color(0xFFE6E9EF);
  static const Color _primary = Color(0xFF4683F6);

  @override
  Widget build(BuildContext context) {
    final controller = Get.put(
      IssueChatController(issue: issue),
      tag: issue.id,
    );
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Scaffold(
      backgroundColor: isDark ? theme.colorScheme.surfaceVariant : _background,
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
          '오늘의 이슈',
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
      body: Column(
        children: [
          // 이슈 정보 헤더
          IssueHeaderCard(
            issue: issue,
            onTap: () => Get.to(() => IssueArticleScreen(issue: issue)),
          ),
          // 연결 상태 배너
          Obx(
            () => _buildConnectionBanner(
              context: context,
              isDark: isDark,
              isConnected: controller.isConnected.value,
              isReconnecting: controller.isReconnecting.value,
            ),
          ),

          // 채팅 메시지 영역
          Expanded(
            child: Obx(() {
              if (controller.isLoading.value) {
                return Center(
                  child: CircularProgressIndicator(
                    color: isDark ? theme.colorScheme.primary : _primary,
                  ),
                );
              }

              if (controller.messages.isEmpty) {
                return _buildEmptyState(context, isDark);
              }

              return ListView.builder(
                controller: controller.scrollController,
                padding: const EdgeInsets.fromLTRB(16, 4, 16, 16),
                keyboardDismissBehavior:
                    ScrollViewKeyboardDismissBehavior.onDrag,
                itemCount: controller.messages.length,
                itemBuilder: (context, index) {
                  final message = controller.messages[index];
                  return ChatMessageBubble(
                    message: message,
                    onReactionTap: () => controller.toggleReaction(message.id),
                  );
                },
              );
            }),
          ),

          // 메시지 입력창
          Obx(
            () => ChatInputField(
              controller: controller.textController,
              onSend: controller.sendMessage,
              isEnabled:
                  !controller.isSending.value && controller.isConnected.value,
            ),
          ),
        ],
      ),
    );
  }

  /// 빈 상태 위젯
  Widget _buildEmptyState(BuildContext context, bool isDark) {
    final theme = Theme.of(context);

    return Center(
      child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          Icon(
            PhosphorIconsRegular.chatCircle,
            size: 64,
            color: isDark ? theme.colorScheme.outline : Colors.grey[300],
          ),
          const SizedBox(height: 16),
          Text(
            '대화를 시작해보세요!',
            style: TextStyle(
              fontSize: 16,
              fontWeight: FontWeight.w700,
              color: isDark ? theme.colorScheme.onSurface : Colors.grey[700],
            ),
          ),
          const SizedBox(height: 8),
          Text(
            '첫 메시지를 보내고 다른 사람들과\n이슈에 대해 이야기를 나눠보세요.',
            textAlign: TextAlign.center,
            style: TextStyle(
              fontSize: 14,
              color: isDark
                  ? theme.colorScheme.onSurfaceVariant
                  : Colors.grey[500],
              height: 1.5,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConnectionBanner({
    required BuildContext context,
    required bool isDark,
    required bool isConnected,
    required bool isReconnecting,
  }) {
    final theme = Theme.of(context);
    final isOffline = !isConnected;
    final message = isOffline
        ? (isReconnecting ? '재연결 중입니다…' : '연결이 끊겼습니다. 다시 시도 중…')
        : '';

    return AnimatedContainer(
      duration: const Duration(milliseconds: 200),
      curve: Curves.easeOut,
      height: isOffline ? 36 : 0,
      child: isOffline
          ? Container(
              width: double.infinity,
              margin: const EdgeInsets.fromLTRB(16, 0, 16, 8),
              padding: const EdgeInsets.symmetric(horizontal: 12),
              decoration: BoxDecoration(
                color: isDark
                    ? const Color(0xFFF59E0B).withValues(alpha: 0.18)
                    : const Color(0xFFFFF4E5),
                borderRadius: BorderRadius.circular(10),
                border: Border.all(
                  color: isDark
                      ? const Color(0xFFF59E0B).withValues(alpha: 0.45)
                      : const Color(0xFFF3D6B0),
                  width: 1,
                ),
              ),
              child: Row(
                children: [
                  Icon(
                    PhosphorIconsRegular.warningCircle,
                    size: 16,
                    color: isDark
                        ? theme.colorScheme.onSurface
                        : const Color(0xFFB76A00),
                  ),
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      message,
                      style: TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: isDark
                            ? theme.colorScheme.onSurface
                            : const Color(0xFFB76A00),
                      ),
                    ),
                  ),
                ],
              ),
            )
          : const SizedBox.shrink(),
    );
  }
}
