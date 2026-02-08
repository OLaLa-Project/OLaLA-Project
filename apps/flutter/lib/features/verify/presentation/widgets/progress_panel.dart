import 'package:flutter/material.dart';

class ProgressStep {
  final String indexLabel; // '1', '2', '3'
  final String title;
  final String description;

  const ProgressStep({
    required this.indexLabel,
    required this.title,
    required this.description,
  });
}

class ProgressPanel extends StatelessWidget {
  final int currentStep; // 0..steps.length-1
  final List<ProgressStep> steps;

  const ProgressPanel({
    super.key,
    required this.currentStep,
    required this.steps,
  });

  @override
  Widget build(BuildContext context) {
    final safeStep = currentStep.clamp(0, steps.length - 1);

    return Column(
      children: [
        for (int i = 0; i < steps.length; i++) ...[
          _StepCard(step: steps[i], state: _resolveState(i, safeStep)),
          if (i != steps.length - 1) const SizedBox(height: 12),
        ],
      ],
    );
  }

  _StepState _resolveState(int i, int current) {
    if (i < current) return _StepState.done;
    if (i == current) return _StepState.active;
    return _StepState.upcoming;
  }
}

enum _StepState { done, active, upcoming }

class _StepCard extends StatelessWidget {
  final ProgressStep step;
  final _StepState state;

  const _StepCard({
    required this.step,
    required this.state,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    final bg = state == _StepState.active
        ? Colors.white.withOpacity(0.20)
        : Colors.white.withOpacity(0.14);

    final border = Colors.white.withOpacity(
      state == _StepState.active ? 0.26 : 0.18,
    );

    final titleColor = Colors.white.withOpacity(
      state == _StepState.upcoming ? 0.86 : 0.95,
    );
    final descColor = Colors.white.withOpacity(
      state == _StepState.upcoming ? 0.72 : 0.84,
    );

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(18),
        border: Border.all(color: border, width: 1),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          _LeadingCircle(label: step.indexLabel),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        step.title,
                        style: theme.textTheme.titleMedium?.copyWith(
                          color: titleColor,
                          fontWeight: FontWeight.w800,
                          height: 1.1,
                        ),
                      ),
                    ),
                    if (state == _StepState.active) const _TypingDots(),
                    if (state == _StepState.done)
                      Icon(
                        Icons.check_rounded,
                        size: 18,
                        color: Colors.white.withOpacity(0.95),
                      ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  step.description,
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: descColor,
                    height: 1.35,
                    fontWeight: FontWeight.w500,
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _LeadingCircle extends StatelessWidget {
  final String label;
  const _LeadingCircle({required this.label});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 32,
      height: 32,
      alignment: Alignment.center,
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.92),
        shape: BoxShape.circle,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.10),
            blurRadius: 10,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Text(
        label,
        style: const TextStyle(
          color: Colors.black87,
          fontWeight: FontWeight.w900,
          fontSize: 14,
        ),
      ),
    );
  }
}

/// “진행중...” 느낌의 점 애니메이션 (외부 패키지 없이)
class _TypingDots extends StatefulWidget {
  const _TypingDots();

  @override
  State<_TypingDots> createState() => _TypingDotsState();
}

class _TypingDotsState extends State<_TypingDots>
    with SingleTickerProviderStateMixin {
  late final AnimationController _c;

  @override
  void initState() {
    super.initState();
    _c = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat();
  }

  @override
  void dispose() {
    _c.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: _c,
      builder: (_, __) {
        final count = ((_c.value * 3).floor()) % 4; // 0..3
        final dots = '.' * count;
        return Padding(
          padding: const EdgeInsets.only(left: 8),
          child: Text(
            dots.isEmpty ? ' ' : dots,
            style: TextStyle(
              color: Colors.white.withOpacity(0.95),
              fontWeight: FontWeight.w900,
              letterSpacing: 1.2,
            ),
          ),
        );
      },
    );
  }
}
