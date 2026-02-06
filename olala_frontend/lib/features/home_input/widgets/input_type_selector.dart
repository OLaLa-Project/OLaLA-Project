import 'package:flutter/material.dart';
import '../home_input_controller.dart';

class InputTypeSelector extends StatelessWidget {
  final Key? containerKey;
  final InputMode selected;
  final VoidCallback onSelectUrl;
  final VoidCallback onSelectText;

  const InputTypeSelector({
    super.key,
    this.containerKey,
    required this.selected,
    required this.onSelectUrl,
    required this.onSelectText,
  });

  static const Color _primary = Color(0xFF4683F6);
  static const Color _text = Color(0xFF1F1F1F);

  static const double _height = 48.0;
  static const double _radius = 12.0; // ✅ 살짝 키워서 더 고급스럽게

  @override
  Widget build(BuildContext context) {
    final isUrl = selected == InputMode.url;

    return Container(
      key: containerKey,
      height: _height,
      decoration: BoxDecoration(
        color: _primary.withOpacity(0.08), // ✅ 배경 살짝 더 얇게
        borderRadius: BorderRadius.circular(_radius),
        border: Border.all(
          color: _primary.withOpacity(0.18), // ✅ 테두리도 살짝 얇게
          width: 1,
        ),
      ),
      child: Row(
        children: [
          Expanded(
            child: _Segment(
              label: 'URL',
              selected: isUrl,
              onTap: isUrl ? null : onSelectUrl, // ✅ 이미 선택이면 no-op
              isLeft: true,
              textColor: _text,
              primary: _primary,
            ),
          ),
          Expanded(
            child: _Segment(
              label: '문장',
              selected: !isUrl,
              onTap: (!isUrl) ? null : onSelectText,
              isLeft: false,
              textColor: _text,
              primary: _primary,
            ),
          ),
        ],
      ),
    );
  }
}

class _Segment extends StatelessWidget {
  final String label;
  final bool selected;
  final VoidCallback? onTap; // ✅ selected면 null로 disabled
  final bool isLeft;

  final Color textColor;
  final Color primary;

  const _Segment({
    required this.label,
    required this.selected,
    required this.onTap,
    required this.isLeft,
    required this.textColor,
    required this.primary,
  });

  static const double _innerRadius = 10.0; // ✅ 바깥과 계층감
  static const Duration _dur = Duration(milliseconds: 160);

  BorderRadius get _radius => BorderRadius.horizontal(
        left: Radius.circular(isLeft ? _innerRadius : 0),
        right: Radius.circular(isLeft ? 0 : _innerRadius),
      );

  @override
  Widget build(BuildContext context) {
    final unselectedColor = textColor.withOpacity(0.65); // ✅ 더 차분하게

    return Padding(
      padding: const EdgeInsets.all(4),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          borderRadius: _radius,
          onTap: onTap,
          overlayColor: MaterialStateProperty.resolveWith((states) {
            if (states.contains(MaterialState.pressed)) {
              return Colors.black.withOpacity(0.06); // ✅ 눌림 피드백
            }
            return null;
          }),
          child: AnimatedContainer(
            duration: _dur,
            curve: Curves.easeOutCubic, // ✅ 더 자연스러운 톤
            decoration: BoxDecoration(
              color: selected ? primary : Colors.transparent, // ✅ 단색 선택
              borderRadius: _radius,
              // ✅ Segmented는 보통 그림자 제거 (더 프로덕트 느낌)
            ),
            constraints: const BoxConstraints(minHeight: 40), // ✅ 안정감
            child: Center(
              child: AnimatedDefaultTextStyle(
                duration: _dur,
                curve: Curves.easeOutCubic,
                style: TextStyle(
                  color: selected ? Colors.white : unselectedColor,
                  fontSize: 15,
                  fontWeight: selected ? FontWeight.w800 : FontWeight.w700,
                  letterSpacing: -0.2,
                ),
                child: Text(label),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
