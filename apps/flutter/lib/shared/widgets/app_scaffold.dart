import 'package:flutter/material.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

/// 앱 공용 아이콘 버튼
class AppIconButton extends StatefulWidget {
  final IconData icon;
  final IconData? pressedIcon;
  final double size;
  final Color? color;
  final String? tooltip;
  final VoidCallback? onPressed;

  const AppIconButton({
    super.key,
    required this.icon,
    this.pressedIcon,
    this.size = 24.0,
    this.color,
    this.tooltip,
    this.onPressed,
  });

  /// 설정 버튼
  factory AppIconButton.settings({
    Key? key,
    VoidCallback? onPressed,
  }) {
    return AppIconButton(
      key: key,
      icon: PhosphorIconsRegular.gear,
      pressedIcon: PhosphorIconsFill.gear,
      size: 32.0,
      color: Colors.black,
      tooltip: '설정',
      onPressed: onPressed,
    );
  }

  @override
  State<AppIconButton> createState() => _AppIconButtonState();
}

class _AppIconButtonState extends State<AppIconButton> {
  bool _isPressed = false;

  @override
  Widget build(BuildContext context) {
    final currentIcon = _isPressed && widget.pressedIcon != null
        ? widget.pressedIcon!
        : widget.icon;

    return GestureDetector(
      onTapDown: (_) => setState(() => _isPressed = true),
      onTapUp: (_) {
        setState(() => _isPressed = false);
        widget.onPressed?.call();  // ✅ null-safe
      },
      onTapCancel: () => setState(() => _isPressed = false),
      child: Padding(
        padding: const EdgeInsets.all(8.0),
        child: Icon(
          currentIcon,
          size: widget.size,
          color: widget.color ?? Colors.black,
        ),
      ),
    );
  }
}