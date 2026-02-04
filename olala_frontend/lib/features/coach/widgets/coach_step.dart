part of coach_overlay;

class _CloseButton extends StatelessWidget {
  final double size;
  final Future<void> Function() onTap;

  const _CloseButton({required this.size, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return Semantics(
      label: '튜토리얼 닫기',
      button: true,
      child: Tooltip(
        message: '닫기',
        child: InkResponse(
          onTap: onTap,
          radius: size / 2,
          child: SizedBox(
            width: size,
            height: size,
            child: Center(
              child: Icon(
                Icons.close_rounded,
                size: 40,
                color: Colors.white.withOpacity(0.9),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _GuideCard extends StatelessWidget {
  static const double estimatedHeight = 132;

  final int step;
  final int totalSteps;

  final String title;
  final String body;

  final String nextLabel;
  final String finishLabel;

  final VoidCallback? onPrev;
  final VoidCallback? onNext;
  final Future<void> Function()? onFinish;

  const _GuideCard({
    required this.step,
    required this.totalSteps,
    required this.title,
    required this.body,
    required this.nextLabel,
    required this.finishLabel,
    required this.onPrev,
    required this.onNext,
    required this.onFinish,
  });

  @override
  Widget build(BuildContext context) {
    final bool isLast = step == totalSteps;

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: Color(0xFFF7F7F7).withOpacity(0.20),
          width: 1,
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              // 🔵 배지 아이콘
              Container(
                width: 28,
                height: 28,
                decoration: BoxDecoration(
                  color: Colors.white,
                  shape: BoxShape.circle,
                  border: Border.all(
                    color: const Color(0xFF3478F6).withOpacity(0.3),
                    width: 1,
                  ),
                ),
                alignment: Alignment.center,
                child: Text(
                  '$step',
                  style: TextStyle(
                    color: const Color(0xFF3478F6).withOpacity(0.9),
                    fontSize: 14,
                    fontWeight: FontWeight.w900,
                  ),
                ),
              ),

              const SizedBox(width: 12),

              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    color: Color(0xFF202124),
                    fontSize: 16,
                    fontWeight: FontWeight.w900,
                    letterSpacing: -0.2,
                  ),
                ),
              ),

              const SizedBox(width: 10),
              Text(
                '$step/$totalSteps',
                style: TextStyle(
                  color: Color(0xFF2E3134),
                  fontSize: 12,
                  fontWeight: FontWeight.w900,
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Align(
            alignment: Alignment.centerLeft,
            child: Text(
              body,
              style: TextStyle(
                color: Color(0xFF3C4043),
                fontSize: 13,
                fontWeight: FontWeight.w700,
                height: 1.35,
              ),
            ),
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              if (onPrev != null) ...[
                Expanded(
                  child: _SecondaryButton(
                    text: '이전',
                    onTap: () {
                      HapticFeedback.selectionClick();
                      onPrev?.call();
                    },
                  ),
                ),
                const SizedBox(width: 12),
              ],
              Expanded(
                child: isLast
                    ? _FinishButton(text: finishLabel, onTap: onFinish!)
                    : _PrimaryButton(
                        text: nextLabel,
                        onTap: () {
                          HapticFeedback.selectionClick();
                          onNext?.call();
                        },
                      ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _PrimaryButton extends StatelessWidget {
  final String text;
  final VoidCallback onTap;

  const _PrimaryButton({required this.text, required this.onTap});

  static const double _height = 48;
  static const double _radius = 24;

  //다음 버튼
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(_radius),
        border: Border.all(color: const Color(0xFF2F6FE4).withOpacity(0.3)),
      ),
      child: Material(
        color: Color(0xFF3478F6).withOpacity(0.18),
        borderRadius: BorderRadius.circular(_radius),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(_radius),
          child: const SizedBox(
            height: _height,
            child: Center(child: _PrimaryButtonText()),
          ),
        ),
      ),
    );
  }
}

class _PrimaryButtonText extends StatelessWidget {
  const _PrimaryButtonText();

  @override
  Widget build(BuildContext context) {
    final _PrimaryButton parent = context
        .findAncestorWidgetOfExactType<_PrimaryButton>()!;
    return Text(
      parent.text,
      textAlign: TextAlign.center,
      style: const TextStyle(
        color: Color(0xFF202124),
        fontSize: 14,
        fontWeight: FontWeight.w900,
        letterSpacing: -0.2,
      ),
    );
  }
}

//이전 버튼
class _SecondaryButton extends StatelessWidget {
  final String text;
  final VoidCallback onTap;

  const _SecondaryButton({required this.text, required this.onTap});

  static const double _height = 48;
  static const double _radius = 24;

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(_radius),
        border: Border.all(color: const Color(0xFFE0E0E0).withOpacity(0.06)),
      ),
      child: Material(
        color: Color(0xFFEDEDED),
        borderRadius: BorderRadius.circular(_radius),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(_radius),
          child: SizedBox(
            height: _height,
            child: Center(
              child: Text(
                text,
                style: const TextStyle(
                  color: Color(0xFF202124),
                  fontSize: 14,
                  fontWeight: FontWeight.w800,
                  letterSpacing: -0.1,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class _FinishButton extends StatelessWidget {
  final String text;
  final Future<void> Function() onTap;

  const _FinishButton({required this.text, required this.onTap});

  static const double _height = 48;
  static const double _radius = 24;

//검증 시작하기 버튼
  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(_radius),
        border: Border.all(color: const Color(0xFF2F6FE4).withOpacity(0.40)),
      ),
      child: Material(
        color: Color(0xFF3478F6).withOpacity(0.18),
        borderRadius: BorderRadius.circular(_radius),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(_radius),
          child: SizedBox(
            height: _height,
            child: Center(
              child: Text(
                text,
                textAlign: TextAlign.center,
                style: const TextStyle(
                  color: Color(0xFF202124),
                  fontSize: 14,
                  fontWeight: FontWeight.w900,
                  letterSpacing: -0.2,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
