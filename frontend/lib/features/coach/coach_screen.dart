part of coach_overlay;

@immutable
class _OverlayStepSpec {
  final String title;
  final String body;
  final bool useRounded;

  final double holeRadius;
  final double borderRadius;

  const _OverlayStepSpec({
    required this.title,
    required this.body,
    required this.useRounded,
    required this.holeRadius,
    required this.borderRadius,
  });

  static _OverlayStepSpec fromStep(int step) {
    final bool is1 = step == 1;
    final bool is2 = step == 2;

    return _OverlayStepSpec(
      title: is1
          ? '입력 방식을 선택해 보세요'
          : is2
              ? '여기에 내용을 작성해보세요'
              : '이제 검증을 시작해볼까요?',
      body: is1
          ? 'URL 기사라면 URL, 문장/문단이라면 문장을 선택하세요.'
          : is2
              ? '내용을 입력하거나, 복사한 내용을 붙여넣으면\n바로 분석할 수 있어요.'
              : '버튼을 누르면 근거와 함께 신뢰도를 분석해드려요.',

      // ✅ 전부 둥근 형태로 통일: 둥근 모서리 정도
      useRounded: true,
      holeRadius: is1 ? 12 : is2 ? 20 : 28, // 구멍의 둥근 정도
      borderRadius: is1 ? 16 : is2 ? 24 : 32, //테두리의 둥근 정도
    );
  }

  Rect? pickMeasuredRect({
    required Rect? selectorRect,
    required Rect? inputRect,
    required Rect? verifyRect,
  }) {
    // 기존 로직 그대로: step1 selector, step2 input, step3 verify
    return switch (title) {
      '입력 방식을 선택해 보세요' => selectorRect,
      '여기에 내용을 작성해보세요' => inputRect,
      _ => verifyRect,
    };
  }

  double fallbackHeight(double screenHeight) {
    // 기존 로직 그대로: step1 52, step3 56, step2 화면높이*0.45
    if (title == '입력 방식을 선택해 보세요') return 52;
    if (title == '이제 검증을 시작해볼까요?') return 56;
    return screenHeight * 0.45;
  }
}
