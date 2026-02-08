import 'package:flutter/material.dart';

/// 멀티라인 텍스트 입력 필드
///
/// URL 또는 검증할 텍스트를 입력받는 확장형 텍스트 필드
/// Coach 오버레이 타겟 측정을 위해 [containerKey] 전달 가능
class InputField extends StatelessWidget {
  final Key? containerKey;
  final Key? clearButtonKey;
  final TextEditingController controller;
  final String placeholder;
  final VoidCallback onClear;

  const InputField({
    super.key,
    this.containerKey,
    this.clearButtonKey,
    required this.controller,
    required this.placeholder,
    required this.onClear,
  });

  static const Color _brand = Color(0xFF4683F6);
  static const Color _text = Color(0xFF0B1220);
  static const double _radius = 20.0;
  static const double _clearSize = 36.0;

  List<BoxShadow> _shadow(Color primary) => [
    BoxShadow(
      color: primary.withOpacity(0.04),
      blurRadius: 10,
      offset: const Offset(0, 3),
    ),
  ];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final primary = _brand;
    final borderColor = isDark
        ? theme.colorScheme.outlineVariant.withOpacity(0.7)
        : primary.withOpacity(0.18);

    return Container(
      key: containerKey,
      decoration: BoxDecoration(
        color: isDark ? theme.colorScheme.surface : Colors.white,
        borderRadius: BorderRadius.circular(_radius),
        border: Border.all(
          color: borderColor,
          width: 1.2, // 1.5 -> 1.2 (더 정제된 느낌)
        ),
        boxShadow: isDark ? const [] : _shadow(primary),
      ),
      child: Stack(
        children: [
          _buildTextField(theme, isDark),
          _buildClearButton(primary, isDark),
        ],
      ),
    );
  }

  Widget _buildTextField(ThemeData theme, bool isDark) {
    return Padding(
      // 상단 여백 소폭 축소(덜 휑하게)
      padding: const EdgeInsets.fromLTRB(16, 14, 52, 16),
      child: TextField(
        controller: controller,
        maxLines: null,
        expands: true,
        keyboardType: TextInputType.multiline,
        textAlignVertical: TextAlignVertical.top,
        style: TextStyle(
          fontSize: 15,
          height: 1.4,
          fontWeight: FontWeight.w500,
          color: isDark ? theme.colorScheme.onSurface : _text,
        ),
        decoration: InputDecoration(
          border: InputBorder.none,
          hintText: placeholder,
          hintStyle: TextStyle(
            // placeholder 대비 상향(가독성 + 입력 유도)
            color: isDark
                ? theme.colorScheme.onSurfaceVariant.withOpacity(0.7)
                : _text.withOpacity(0.46),
            height: 1.4,
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
    );
  }

  Widget _buildClearButton(Color primary, bool isDark) {
    return Positioned(
      right: 10,
      top: 10,
      child: Material(
        color: primary.withOpacity(isDark ? 0.12 : 0.08),
        shape: const CircleBorder(),
        child: InkWell(
          onTap: onClear,
          customBorder: const CircleBorder(),
          child: SizedBox(
            key: clearButtonKey,
            width: _clearSize,
            height: _clearSize,
            child: Icon(
              Icons.close_rounded,
              size: 20,
              color: primary.withOpacity(isDark ? 0.85 : 0.70),
            ),
          ),
        ),
      ),
    );
  }
}
