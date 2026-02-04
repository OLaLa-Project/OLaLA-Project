import 'package:flutter/material.dart';

/// 멀티라인 텍스트 입력 필드
///
/// URL 또는 검증할 텍스트를 입력받는 확장형 텍스트 필드
/// Coach 오버레이 타겟 측정을 위해 [containerKey] 전달 가능
class InputField extends StatelessWidget {
  final Key? containerKey;
  final TextEditingController controller;
  final String placeholder;
  final VoidCallback onClear;

  const InputField({
    super.key,
    this.containerKey,
    required this.controller,
    required this.placeholder,
    required this.onClear,
  });

  // (디자인 토큰 - 파일 내부)
  static const Color _primary = Color(0xFF4683F6);
  static const Color _text = Color(0xFF0B1220);

  static const double _radius = 20.0;
  static const double _clearSize = 36.0;

  List<BoxShadow> get _shadow => [
        BoxShadow(
          color: _primary.withOpacity(0.04),
          blurRadius: 10,
          offset: const Offset(0, 3),
        ),
      ];

  @override
  Widget build(BuildContext context) {
    return Container(
      key: containerKey,
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(_radius),
        border: Border.all(
          color: _primary.withOpacity(0.18),
          width: 1.2, // 1.5 -> 1.2 (더 정제된 느낌)
        ),
        boxShadow: _shadow,
      ),
      child: Stack(
        children: [
          _buildTextField(),
          _buildClearButton(),
        ],
      ),
    );
  }

  Widget _buildTextField() {
    return Padding(
      // 상단 여백 소폭 축소(덜 휑하게)
      padding: const EdgeInsets.fromLTRB(16, 14, 52, 16),
      child: TextField(
        controller: controller,
        maxLines: null,
        expands: true,
        keyboardType: TextInputType.multiline,
        textAlignVertical: TextAlignVertical.top,
        style: const TextStyle(
          fontSize: 15,
          height: 1.4,
          fontWeight: FontWeight.w500,
          color: _text,
        ),
        decoration: InputDecoration(
          border: InputBorder.none,
          hintText: placeholder,
          hintStyle: TextStyle(
            // placeholder 대비 상향(가독성 + 입력 유도)
            color: _text.withOpacity(0.46),
            height: 1.4,
            fontWeight: FontWeight.w500,
          ),
        ),
      ),
    );
  }

  Widget _buildClearButton() {
    return Positioned(
      right: 8,
      top: 8,
      child: Material(
        color: _primary.withOpacity(0.08), // 0.10 -> 0.08
        borderRadius: BorderRadius.circular(14),
        child: InkWell(
          onTap: onClear,
          borderRadius: BorderRadius.circular(14),
          child: SizedBox(
            width: _clearSize,
            height: _clearSize,
            child: Icon(
              Icons.close_rounded,
              size: 20,
              color: _primary.withOpacity(0.70),
            ),
          ),
        ),
      ),
    );
  }
}
