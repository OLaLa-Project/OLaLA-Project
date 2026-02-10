import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../../app/routes.dart';
import '../home_input/home_input_screen.dart';
import '../shell/shell_controller.dart';
import 'models/daily_issue.dart';
import 'models/chat_message.dart';
import 'issue_chat_controller.dart';
import 'issue_article_screen.dart';
import 'widgets/issue_header_card.dart';
import 'widgets/chat_message_bubble.dart';
import 'widgets/chat_input_field.dart';
import 'widgets/qr_code_dialog.dart';

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
    final controller = Get.isRegistered<IssueChatController>(tag: issue.id)
        ? Get.find<IssueChatController>(tag: issue.id)
        : Get.put(IssueChatController(issue: issue), tag: issue.id);
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
          '오늘의 이슈',
          style: TextStyle(
            fontSize: 18,
            fontWeight: FontWeight.w700,
            color: isDark ? theme.colorScheme.onSurface : _textPrimary,
          ),
        ),
        centerTitle: true,
        actions: [
          // QR 코드 표시 버튼
          IconButton(
            icon: Icon(
              PhosphorIconsRegular.qrCode,
              color: isDark ? theme.colorScheme.onSurface : _textPrimary,
            ),
            onPressed: () => QrCodeDialog.show(context, issue),
            tooltip: 'QR 코드 보기',
          ),
          const SizedBox(width: 8),
        ],
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
                    onRetryTap:
                        message.deliveryStatus == MessageDeliveryStatus.failed
                        ? () => controller.retryMessage(message.id)
                        : null,
                  );
                },
              );
            }),
          ),

          // 이슈 판별 FAB (입력창 위)
          _IssueVerifyFab(isDark: isDark, onTap: _openHomeInputForVerification),

          // 메시지 입력창
          Obx(
            () => ChatInputField(
              controller: controller.textController,
              onSend: controller.sendMessage,
              isEnabled: !controller.isSending.value,
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

  void _openHomeInputForVerification() {
    if (Get.isRegistered<ShellController>()) {
      final shellController = Get.find<ShellController>();
      shellController.setTab(1);

      var foundShellRoute = false;
      Get.until((route) {
        final isShell = route.settings.name == AppRoutes.shell;
        if (isShell) {
          foundShellRoute = true;
        }
        return isShell || route.isFirst;
      });

      if (foundShellRoute || Get.currentRoute == AppRoutes.shell) {
        return;
      }
    }

    Get.to(() => const HomeInputScreen());
  }
}

class _IssueVerifyFab extends StatelessWidget {
  const _IssueVerifyFab({required this.isDark, required this.onTap});

  final bool isDark;
  final VoidCallback onTap;

  static const Color _fab = Color(0xFF4683F6);
  static const Color _border = Color(0xFFE4E8F1);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Align(
      alignment: Alignment.centerRight,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(16, 0, 10, 8),
        child: Tooltip(
          message: '이슈 판별하기',
          child: Material(
            color: Colors.transparent,
            shape: const CircleBorder(),
            child: InkWell(
              onTap: onTap,
              customBorder: const CircleBorder(),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 180),
                curve: Curves.easeOut,
                width: 50,
                height: 50,
                decoration: BoxDecoration(
                  color: _fab,
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: isDark ? theme.colorScheme.outlineVariant : _border,
                    width: 1.2,
                  ),
                  boxShadow: [
                    BoxShadow(
                      color: _fab.withValues(alpha: isDark ? 0.44 : 0.32),
                      blurRadius: 14,
                      offset: const Offset(0, 5),
                    ),
                  ],
                ),
                child: const Icon(
                  PhosphorIconsRegular.magnifyingGlass,
                  size: 24,
                  color: Colors.white,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
