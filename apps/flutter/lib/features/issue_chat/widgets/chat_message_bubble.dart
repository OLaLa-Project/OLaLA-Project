import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../models/chat_message.dart';
import 'message_reaction.dart';

/// 채팅 메시지 말풍선 위젯
class ChatMessageBubble extends StatelessWidget {
  final ChatMessage message;
  final VoidCallback onReactionTap;

  const ChatMessageBubble({
    super.key,
    required this.message,
    required this.onReactionTap,
  });

  static const Color _primary = Color(0xFF4683F6);
  static const Color _textPrimary = Color(0xFF1F1F1F);
  static const Color _textTertiary = Color(0xFF9AA1AD);
  static const Color _surfaceAlt = Color(0xFFF2F4F7);
  static const Color _border = Color(0xFFE6E9EF);

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    if (message.isMine) {
      return _buildMyMessage(theme, isDark);
    } else {
      return _buildOtherMessage(theme, isDark);
    }
  }

  /// 내 메시지 (오른쪽 정렬)
  Widget _buildMyMessage(ThemeData theme, bool isDark) {
    return Padding(
      padding: const EdgeInsets.only(left: 56, bottom: 10),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.end,
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          // 시간
          Padding(
            padding: const EdgeInsets.only(right: 6, bottom: 2),
            child: Text(
              _formatTime(message.timestamp),
              style: TextStyle(
                fontSize: 11,
                fontWeight: FontWeight.w500,
                color: isDark ? theme.colorScheme.outline : _textTertiary,
              ),
            ),
          ),
          // 메시지 버블
          Flexible(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                DecoratedBox(
                  decoration: BoxDecoration(
                    color: _primary,
                    borderRadius: const BorderRadius.only(
                      topLeft: Radius.circular(16),
                      topRight: Radius.circular(16),
                      bottomLeft: Radius.circular(16),
                      bottomRight: Radius.circular(6),
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: _primary.withOpacity(0.16),
                        blurRadius: 8,
                        offset: const Offset(0, 2),
                      ),
                    ],
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 10,
                    ),
                    child: Text(
                      message.content,
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w500,
                        color: Colors.white,
                        height: 1.4,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 6),
                // 반응 버튼
                MessageReaction(
                  count: message.reactionCount,
                  isReacted: message.isReactedByMe,
                  onTap: onReactionTap,
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  /// 다른 사용자 메시지 (왼쪽 정렬)
  Widget _buildOtherMessage(ThemeData theme, bool isDark) {
    final avatarColor = _avatarColorFor(message.userId, message.username);
    final initial = _initialFor(message.username);

    return Padding(
      padding: const EdgeInsets.only(right: 56, bottom: 10),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // 프로필 아바타
          Container(
            width: 36,
            height: 36,
            decoration: BoxDecoration(
              color: avatarColor.withOpacity(0.16),
              shape: BoxShape.circle,
              border: Border.all(
                color: avatarColor.withOpacity(0.35),
                width: 0.8,
              ),
            ),
            child: Center(
              child: Text(
                initial,
                style: TextStyle(
                  fontSize: 16,
                  fontWeight: FontWeight.w700,
                  color: avatarColor,
                ),
              ),
            ),
          ),
          const SizedBox(width: 8),
          // 메시지 영역
          Flexible(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                // 닉네임
                Padding(
                  padding: const EdgeInsets.only(left: 4, bottom: 4),
                  child: Text(
                    message.username,
                    style: TextStyle(
                      fontSize: 12,
                      fontWeight: FontWeight.w700,
                      color: isDark
                          ? theme.colorScheme.onSurface
                          : _textPrimary,
                    ),
                  ),
                ),
                // 메시지 버블
                DecoratedBox(
                  decoration: BoxDecoration(
                    color: isDark
                        ? theme.colorScheme.surfaceContainerHighest
                        : _surfaceAlt,
                    borderRadius: const BorderRadius.only(
                      topLeft: Radius.circular(6),
                      topRight: Radius.circular(16),
                      bottomLeft: Radius.circular(16),
                      bottomRight: Radius.circular(16),
                    ),
                    border: Border.all(
                      color: isDark
                          ? theme.colorScheme.outlineVariant
                          : _border,
                      width: 1,
                    ),
                  ),
                  child: Padding(
                    padding: const EdgeInsets.symmetric(
                      horizontal: 14,
                      vertical: 10,
                    ),
                    child: Text(
                      message.content,
                      style: TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.w500,
                        color: isDark
                            ? theme.colorScheme.onSurface
                            : _textPrimary,
                        height: 1.4,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 6),
                // 시간 + 반응
                Row(
                  children: [
                    Padding(
                      padding: const EdgeInsets.only(left: 4),
                      child: Text(
                        _formatTime(message.timestamp),
                        style: TextStyle(
                          fontSize: 11,
                          fontWeight: FontWeight.w500,
                          color: isDark
                              ? theme.colorScheme.outline
                              : _textTertiary,
                        ),
                      ),
                    ),
                    const SizedBox(width: 8),
                    MessageReaction(
                      count: message.reactionCount,
                      isReacted: message.isReactedByMe,
                      onTap: onReactionTap,
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  String _formatTime(DateTime timestamp) {
    final now = DateTime.now();
    final diff = now.difference(timestamp);

    if (diff.inDays == 0) {
      // 오늘: 시간만 표시
      return DateFormat('HH:mm').format(timestamp);
    } else if (diff.inDays == 1) {
      // 어제
      return '어제 ${DateFormat('HH:mm').format(timestamp)}';
    } else {
      // 그 외: 날짜 + 시간
      return DateFormat('MM/dd HH:mm').format(timestamp);
    }
  }

  Color _avatarColorFor(String userId, String username) {
    final seed = userId.trim().isNotEmpty ? userId : username;
    if (seed.isEmpty) {
      return _primary;
    }

    var hash = 0;
    for (final unit in seed.codeUnits) {
      hash = 0x1fffffff & (hash + unit);
      hash = 0x1fffffff & (hash + ((0x0007ffff & hash) << 10));
      hash ^= (hash >> 6);
    }
    hash = 0x1fffffff & (hash + ((0x03ffffff & hash) << 3));
    hash ^= (hash >> 11);
    hash = 0x1fffffff & (hash + ((0x00003fff & hash) << 15));

    final hue = (hash % 360).toDouble();
    return HSLColor.fromAHSL(1, hue, 0.42, 0.58).toColor();
  }

  String _initialFor(String username) {
    final trimmed = username.trim();
    if (trimmed.isEmpty) {
      return '?';
    }
    return trimmed.characters.first;
  }
}
