import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

/// 메시지 반응 (좋아요) 버튼
class MessageReaction extends StatelessWidget {
  final int count;
  final bool isReacted;
  final VoidCallback onTap;

  const MessageReaction({
    super.key,
    required this.count,
    required this.isReacted,
    required this.onTap,
  });

  static const Color _activeColor = Color(0xFFE5484D);
  static const Color _inactiveColor = Color(0xFF9AA1AD);
  static const Color _border = Color(0xFFE6E9EF);

  @override
  Widget build(BuildContext context) {
    final foreground = isReacted ? _activeColor : _inactiveColor;

    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: AnimatedContainer(
          duration: const Duration(milliseconds: 180),
          curve: Curves.easeOut,
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: isReacted ? _activeColor.withOpacity(0.12) : Colors.transparent,
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: isReacted ? _activeColor.withOpacity(0.2) : _border,
              width: 1,
            ),
          ),
          child: Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                isReacted
                    ? PhosphorIconsFill.heart
                    : PhosphorIconsRegular.heart,
                size: 16,
                color: foreground,
              ),
              if (count > 0) ...[
                const SizedBox(width: 4),
                Text(
                  '$count',
                  style: TextStyle(
                    fontSize: 12,
                    fontWeight: FontWeight.w600,
                    color: foreground,
                  ),
                ),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
