import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

class ShareButton extends StatelessWidget {
  final VoidCallback? onPressed;

  const ShareButton({super.key, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return _ResultActionButton(
      label: '공유',
      icon: PhosphorIconsLight.export,
      onPressed: onPressed,
      backgroundColor: const Color(0xFF3478F6),
      iconColor: Colors.white,
    );
  }
}

class BookmarkButton extends StatelessWidget {
  final VoidCallback? onPressed;

  const BookmarkButton({super.key, required this.onPressed});

  @override
  Widget build(BuildContext context) {
    return _ResultActionButton(
      label: '북마크 추가',
      icon: PhosphorIconsLight.bookmarkSimple,
      onPressed: onPressed,
      backgroundColor: Colors.white,
      iconColor: const Color(0xFF3478F6),
      borderColor: const Color(0xFF3478F6),
    );
  }
}

class _ResultActionButton extends StatelessWidget {
  final VoidCallback? onPressed;
  final String label;
  final IconData icon;
  final Color backgroundColor;
  final Color iconColor;
  final Color? borderColor;

  const _ResultActionButton({
    required this.onPressed,
    required this.label,
    required this.icon,
    required this.backgroundColor,
    required this.iconColor,
    this.borderColor,
  });

  @override
  Widget build(BuildContext context) {
    final enabled = onPressed != null;

    return Material(
      color: Colors.transparent,
      child: Semantics(
        button: true,
        label: label,
        enabled: enabled,
        child: Tooltip(
          message: label,
          child: InkWell(
            onTap: onPressed,
            borderRadius: BorderRadius.circular(18),
            child: Ink(
              width: 48,
              height: 48,
              decoration: BoxDecoration(
                color: backgroundColor.withOpacity( enabled ? 1 : 0.5),
                borderRadius: BorderRadius.circular(18),
                border: borderColor == null
                    ? null
                    : Border.all(
                        color: borderColor!.withOpacity(
                          enabled ? 0.35 : 0.2,
                        ),
                      ),
              ),
              child: Icon(
                icon,
                color: iconColor.withOpacity( enabled ? 1 : 0.7),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
