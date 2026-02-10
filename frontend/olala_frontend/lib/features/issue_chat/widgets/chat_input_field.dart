import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

/// 채팅 메시지 입력창
class ChatInputField extends StatelessWidget {
  final TextEditingController controller;
  final VoidCallback onSend;
  final bool isEnabled;

  const ChatInputField({
    super.key,
    required this.controller,
    required this.onSend,
    this.isEnabled = true,
  });

  static const Color _primary = Color(0xFF4683F6);
  static const Color _border = Color(0xFFE6E9EF);
  static const Color _fieldBg = Color(0xFFF3F4F7);
  static const Color _textPrimary = Color(0xFF1F1F1F);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return SafeArea(
      top: false,
      child: ValueListenableBuilder<TextEditingValue>(
        valueListenable: controller,
        builder: (context, value, child) {
          final hasText = value.text.trim().isNotEmpty;
          final canSend = isEnabled && hasText;

          return Container(
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            decoration: BoxDecoration(
              color: isDark ? theme.colorScheme.surface : Colors.white,
              border: Border(
                top: BorderSide(
                  color: isDark ? theme.colorScheme.outlineVariant : _border,
                  width: 1,
                ),
              ),
            ),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                // 입력 필드
                Expanded(
                  child: Container(
                    constraints: const BoxConstraints(
                      minHeight: 40,
                      maxHeight: 120,
                    ),
                    decoration: BoxDecoration(
                      color: isDark
                          ? theme.colorScheme.surfaceContainerHighest
                          : _fieldBg,
                      borderRadius: BorderRadius.circular(24),
                      border: Border.all(
                        color: isDark
                            ? theme.colorScheme.outlineVariant
                            : _border,
                        width: 1,
                      ),
                    ),
                    child: TextField(
                      controller: controller,
                      enabled: isEnabled,
                      maxLines: null,
                      maxLength: 500,
                      textInputAction: TextInputAction.newline,
                      decoration: InputDecoration(
                        hintText: '메시지를 입력하세요...',
                        hintStyle: TextStyle(
                          fontSize: 15,
                          color: isDark
                              ? theme.colorScheme.onSurfaceVariant
                              : Colors.grey[500],
                        ),
                        border: InputBorder.none,
                        contentPadding: const EdgeInsets.symmetric(
                          horizontal: 18,
                          vertical: 10,
                        ),
                        counterText: '',
                      ),
                      style: TextStyle(
                        fontSize: 15,
                        color: isDark
                            ? theme.colorScheme.onSurface
                            : _textPrimary,
                      ),
                    ),
                  ),
                ),
                const SizedBox(width: 10),
                // 전송 버튼
                Material(
                  color: Colors.transparent,
                  shape: const CircleBorder(),
                  child: InkWell(
                    onTap: canSend ? onSend : null,
                    customBorder: const CircleBorder(),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 160),
                      curve: Curves.easeOut,
                      width: 42,
                      height: 42,
                      decoration: BoxDecoration(
                        color: canSend
                            ? _primary
                            : (isDark
                                  ? theme.colorScheme.outlineVariant
                                  : Colors.grey[300]),
                        shape: BoxShape.circle,
                        boxShadow: [
                          if (canSend)
                            BoxShadow(
                              color: _primary.withValues(alpha: 0.22),
                              blurRadius: 8,
                              offset: const Offset(0, 2),
                            ),
                        ],
                      ),
                      child: Center(
                        child: Icon(
                          PhosphorIconsFill.paperPlaneTilt,
                          size: 20,
                          color: canSend
                              ? Colors.white
                              : (isDark
                                    ? theme.colorScheme.onSurfaceVariant
                                    : Colors.grey[500]),
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          );
        },
      ),
    );
  }
}
