import 'package:flutter/material.dart';

/// 검증 시작 버튼 (CTA)
///
/// - 단색 배경(브랜드 컬러)
/// - 로딩 상태: 버튼 비활성 + 스피너 표시 + 색상 톤 다운
/// - Coach 오버레이 타겟 측정을 위해 [containerKey] 전달 가능
class VerifyStartButton extends StatelessWidget {
  final Key? containerKey;
  final VoidCallback onPressed;
  final bool isLoading;
  final String text;

  const VerifyStartButton({
    super.key,
    this.containerKey,
    required this.onPressed,
    this.isLoading = false,
    this.text = '검증 시작하기',
  });

  // Design tokens
  static const Color _primary = Color(0xFF4683F6);
  static const double _height = 56.0;
  static const double _radius = 28.0;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      key: containerKey,
      height: _height,
      width: double.infinity,
      child: ElevatedButton(
        onPressed: isLoading ? null : onPressed,
        style: ButtonStyle(
          padding: const MaterialStatePropertyAll(EdgeInsets.zero),
          elevation: const MaterialStatePropertyAll(0),
          backgroundColor: const MaterialStatePropertyAll(Colors.transparent),
          shape: MaterialStatePropertyAll(
            RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(_radius),
            ),
          ),
          overlayColor: MaterialStateProperty.resolveWith((states) {
            if (states.contains(MaterialState.pressed)) {
              return Colors.black.withOpacity(0.08);
            }
            return null;
          }),
        ),
        child: Ink(
          decoration: BoxDecoration(
            color: isLoading ? _primary.withOpacity(0.5) : _primary,
            borderRadius: BorderRadius.circular(_radius),
          ),
          child: Center(
            child: isLoading ? _buildLoading() : _buildText(),
          ),
        ),
      ),
    );
  }

  Widget _buildText() {
    return Text(
      text,
      style: const TextStyle(
        fontSize: 17,
        fontWeight: FontWeight.w700,
        color: Colors.white,
      ),
    );
  }

  Widget _buildLoading() {
    return const SizedBox(
      width: 22,
      height: 22,
      child: CircularProgressIndicator(
        strokeWidth: 2.5,
        color: Colors.white,
      ),
    );
  }
}
