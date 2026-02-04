library coach_overlay;

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

part '../coach_screen.dart';
part 'coach_progress.dart';
part 'coach_step.dart';

class CoachOverlay extends StatefulWidget {
  final int coachStep;
  final VoidCallback onClose;
  final VoidCallback onNext;
  final VoidCallback onPrev;
  final VoidCallback onFinish;

  final Rect? selectorRect;
  final Rect? inputRect;
  final Rect? verifyRect;

  const CoachOverlay({
    super.key,
    required this.coachStep,
    required this.onClose,
    required this.onNext,
    required this.onPrev,
    required this.onFinish,
    required this.selectorRect,
    required this.inputRect,
    required this.verifyRect,
  });

  @override
  State<CoachOverlay> createState() => _CoachOverlayState();
}

class _CoachOverlayState extends State<CoachOverlay>
    with SingleTickerProviderStateMixin {
  late final AnimationController _fade;
  late final Animation<double> _opacity;

  bool _isClosing = false;

  static const Color coachDimColor = Color(0xFF000000);
  static const Color coachHighlightColor = Color(0xFF5A9CFF);
  static const Color coachTextDark = Color(0xFF1A1A2E);

  static const int _totalSteps = 3;

  static const Duration _fadeDuration = Duration(milliseconds: 220);
  static const Curve _fadeCurve = Curves.easeOutCubic;

  static const double _closeRight = 16.0;

  @override
  void initState() {
    super.initState();
    _fade = AnimationController(vsync: this, duration: _fadeDuration)
      ..forward();
    _opacity = CurvedAnimation(parent: _fade, curve: _fadeCurve);
  }

  @override
  void dispose() {
    _fade.dispose();
    super.dispose();
  }

  Future<void> _dismissThen(VoidCallback callback) async {
    if (_isClosing) return;
    _isClosing = true;

    try {
      await _fade.reverse(); // 먼저 사라짐
    } catch (_) {
      // ignore
    }

    callback(); // 그 다음 실제 종료(showCoach=false)
  }

  @override
  Widget build(BuildContext context) {
    final Size size = MediaQuery.sizeOf(context);
    final EdgeInsets padding = MediaQuery.paddingOf(context);

    final int step = widget.coachStep.clamp(1, _totalSteps);
    final _OverlayStepSpec spec = _OverlayStepSpec.fromStep(step);

    final Rect? measured = spec.pickMeasuredRect(
      selectorRect: widget.selectorRect,
      inputRect: widget.inputRect,
      verifyRect: widget.verifyRect,
    );

    final Rect fallback = Rect.fromLTWH(
      24,
      padding.top + 120,
      size.width - 48,
      spec.fallbackHeight(size.height),
    );

    final Rect highlightRect = measured ?? fallback;

    // 설정 아이콘과 동일한 위치 계산
    final double closeTop = padding.top + 8; // AppBar(64) 기준 정렬

    // 항상 하이라이트 아래에 카드 배치
    final double guideTop = highlightRect.bottom + 16;
    final double guideTopClamped = guideTop.clamp(
      padding.top + 12,
      size.height - 12 - _GuideCard.estimatedHeight,
    );

    const String nextLabel = '다음';
    const String finishLabel = '검증 시작하기';

    return FadeTransition(
      opacity: _opacity,
      child: Material(
        color: Colors.transparent,
        child: Stack(
          children: [
            Positioned.fill(
              child: CustomPaint(
                painter: _CoachDimPainter(
                  hole: highlightRect,
                  holeRadius: spec.holeRadius,
                  useRounded: spec.useRounded,
                  dimColor: coachDimColor.withOpacity(0.6),
                ),
              ),
            ),
            Positioned.fromRect(
              rect: highlightRect.inflate(3),
              child: IgnorePointer(
                child: DecoratedBox(
                  decoration: BoxDecoration(
                    borderRadius: spec.useRounded
                        ? BorderRadius.circular(spec.borderRadius)
                        : BorderRadius.zero,
                    border: Border.all(color: Colors.white, width: 3),
                  ),
                ),
              ),
            ),
            // ✅ 오버레이 상단바 중앙 안내 문구
            Positioned.fill(
              top: closeTop,
              bottom: null,
              child: IgnorePointer(
                child: Align(
                  alignment: Alignment.topCenter,
                  child: SizedBox(
                    height: 44, // AppBar 터치 영역과 동일 높이
                    child: Center(
                      child: Text(
                        '검증 방법을 알려드릴게요',
                        maxLines: 1,
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(
                          color: Colors.white.withOpacity(0.92),
                          fontSize: 18,
                          fontWeight: FontWeight.w800,
                          letterSpacing: -0.2,
                        ),
                      ),
                    ),
                  ),
                ),
              ),
            ),

            Positioned(
              right: _closeRight,
              top: closeTop,
              child: _CloseButton(
                size: 44,
                onTap: () async {
                  HapticFeedback.lightImpact();
                  await _dismissThen(widget.onClose);
                },
              ),
            ),
            Positioned(
              left: 24,
              right: 24,
              top: guideTopClamped,
              child: _GuideCard(
                step: step,
                totalSteps: _totalSteps,
                title: spec.title,
                body: spec.body,
                nextLabel: nextLabel,
                finishLabel: finishLabel,
                onPrev: step == 1 ? null : widget.onPrev,
                onNext: step == _totalSteps ? null : widget.onNext,
                onFinish: step == _totalSteps
                    ? () async {
                        HapticFeedback.mediumImpact();
                        await _dismissThen(widget.onFinish);
                      }
                    : null,
              ),
            ),
          ],
        ),
      ),
    );
  }
}
