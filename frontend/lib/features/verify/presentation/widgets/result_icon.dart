import 'package:flutter/material.dart';
import '../result_controller.dart';

class ResultIcon extends StatelessWidget {
  final VerdictType verdict;
  final double size;

  const ResultIcon({
    super.key,
    required this.verdict,
    this.size = 84,  // 기본값 84 (기존 크기 유지)
  });

  @override
  Widget build(BuildContext context) {
    final s = _style(verdict);
    final iconSize = size * 0.52;  // 아이콘 크기는 컨테이너의 약 52%
    final borderRadius = size * 0.31;  // 둥근 모서리 비율 유지

    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: s.bg,
        borderRadius: BorderRadius.circular(borderRadius),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity( 0.06),
            blurRadius: 18,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Icon(s.icon, size: iconSize, color: s.fg),
    );
  }

  _IconStyle _style(VerdictType v) {
    switch (v) {
      case VerdictType.trueClaim:
        return const _IconStyle(
          bg: Color(0xFFE8F9EA),
          fg: Color(0xFF34C759),
          icon: Icons.verified_rounded,
        );
      case VerdictType.falseClaim:
        return const _IconStyle(
          bg: Color(0xFFFFEAEA),
          fg: Color(0xFFEF4444),
          icon: Icons.cancel_rounded,
        );
      case VerdictType.mixed:
        return const _IconStyle(
          bg: Color(0xFFFFF4E6),
          fg: Color(0xFFF59E0B),
          icon: Icons.info_rounded,
        );
      case VerdictType.unverified:
        return const _IconStyle(
          bg: Color(0xFFF2F4F7),
          fg: Color(0xFF667085),
          icon: Icons.help_rounded,
        );
    }
  }
}

class _IconStyle {
  final Color bg;
  final Color fg;
  final IconData icon;
  const _IconStyle({required this.bg, required this.fg, required this.icon});
}
