import 'package:flutter/material.dart';

class ResultHeader extends StatelessWidget {
  final VoidCallback onBack;
  final VoidCallback onSettings;
  final String logoAsset;

  const ResultHeader({
    super.key,
    required this.onBack,
    required this.onSettings,
    required this.logoAsset,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 8),
      child: Row(
        children: [
          _IconButton(icon: Icons.arrow_back_ios_new_rounded, onTap: onBack),
          const SizedBox(width: 8),
          Expanded(
            child: Center(child: _Logo(logoAsset: logoAsset)),
          ),
          const SizedBox(width: 8),
          _IconButton(icon: Icons.settings_rounded, onTap: onSettings),
        ],
      ),
    );
  }
}

class _Logo extends StatelessWidget {
  final String logoAsset;

  const _Logo({required this.logoAsset});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Container(
      height: 36,
      padding: const EdgeInsets.symmetric(horizontal: 14),
      decoration: BoxDecoration(
        color: isDark ? theme.colorScheme.surface : Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border.all(
          color: isDark
              ? theme.colorScheme.outlineVariant
              : const Color(0xFFE6ECFF),
        ),
        boxShadow: isDark
            ? const []
            : [
                BoxShadow(
                  color: Colors.black.withOpacity(0.04),
                  blurRadius: 14,
                  offset: const Offset(0, 6),
                ),
              ],
      ),
      alignment: Alignment.center,
      child: Image.asset(
        logoAsset,
        height: 18,
        fit: BoxFit.contain,
        errorBuilder: (_, __, ___) {
          // 로고 에셋 없을 때 안전 처리
          return const Text(
            'OLaLA',
            style: TextStyle(fontWeight: FontWeight.w900),
          );
        },
      ),
    );
  }
}

class _IconButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;

  const _IconButton({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14),
      child: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: isDark ? theme.colorScheme.surface : Colors.white,
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: isDark
                ? theme.colorScheme.outlineVariant
                : const Color(0xFFE6ECFF),
          ),
        ),
        child: Icon(
          icon,
          color: isDark ? theme.colorScheme.onSurface : const Color(0xFF111827),
        ),
      ),
    );
  }
}
