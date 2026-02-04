import 'package:flutter/material.dart';

/// 튜토리얼 단계 데이터 모델
class TutorialStep {
  final String title;
  final String description;
  final IconData icon;

  const TutorialStep({
    required this.title,
    required this.description,
    required this.icon,
  });
}

/// 튜토리얼 단계별 콘텐츠 정의
abstract final class TutorialContent {
  static const List<TutorialStep> steps = [
    TutorialStep(
      title: 'URL 또는 텍스트 선택',
      description: '검증하고 싶은 콘텐츠의 유형을 선택하세요.\n'
          'URL을 선택하면 웹 페이지의 내용을,\n'
          'Text를 선택하면 직접 입력한 문장을 검증합니다.',
      icon: Icons.toggle_on_outlined,
    ),
    TutorialStep(
      title: '검증할 내용 입력',
      description: '검증하고 싶은 URL을 붙여넣거나\n'
          '팩트체크가 필요한 문장을 입력하세요.\n'
          'AI가 신뢰도를 분석합니다.',
      icon: Icons.edit_note_outlined,
    ),
    TutorialStep(
      title: '검증 시작',
      description: '버튼을 누르면 AI가 입력된 내용의\n'
          '사실 여부를 분석하고 결과를 알려드립니다.\n'
          '검증에는 잠시 시간이 소요될 수 있습니다.',
      icon: Icons.fact_check_outlined,
    ),
  ];

  static int get totalSteps => steps.length;
}

/// 튜토리얼 카드 위젯
class TutorialCard extends StatelessWidget {
  final TutorialStep step;
  final int stepNumber;
  final int totalSteps;

  const TutorialCard({
    super.key,
    required this.step,
    required this.stepNumber,
    required this.totalSteps,
  });

  static const _primaryColor = Color(0xFF87CEEB);
  static const _primaryDark = Color(0xFF5DADE2);
  static const _textColor = Color(0xFF0B1220);

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color: _primaryColor.withOpacity(0.08),
            blurRadius: 16,
            offset: const Offset(0, 4),
          ),
        ],
        border: Border.all(
          color: _primaryColor.withOpacity(0.15),
          width: 1,
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          _StepIndicator(current: stepNumber, total: totalSteps),
          const SizedBox(height: 16),
          _IconCircle(icon: step.icon),
          const SizedBox(height: 16),
          _TitleText(text: step.title),
          const SizedBox(height: 12),
          _DescriptionText(text: step.description),
        ],
      ),
    );
  }
}

/// 단계 표시기 (도트)
class _StepIndicator extends StatelessWidget {
  final int current;
  final int total;

  const _StepIndicator({required this.current, required this.total});

  static const _primaryColor = Color(0xFF87CEEB);

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.center,
      children: List.generate(total, (index) {
        final isActive = index == current - 1;
        return AnimatedContainer(
          duration: const Duration(milliseconds: 200),
          margin: const EdgeInsets.symmetric(horizontal: 4),
          width: isActive ? 24 : 8,
          height: 8,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(4),
            color: isActive ? _primaryColor : _primaryColor.withOpacity(0.3),
          ),
        );
      }),
    );
  }
}

/// 아이콘 서클
class _IconCircle extends StatelessWidget {
  final IconData icon;

  const _IconCircle({required this.icon});

  static const _primaryColor = Color(0xFF87CEEB);
  static const _primaryDark = Color(0xFF5DADE2);

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 72,
      height: 72,
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        gradient: const LinearGradient(
          colors: [_primaryColor, _primaryDark],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        boxShadow: [
          BoxShadow(
            color: _primaryColor.withOpacity(0.25),
            blurRadius: 10,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Icon(icon, size: 36, color: Colors.white),
    );
  }
}

/// 제목 텍스트
class _TitleText extends StatelessWidget {
  final String text;

  const _TitleText({required this.text});

  static const _textColor = Color(0xFF0B1220);

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: const TextStyle(
        fontSize: 20,
        fontWeight: FontWeight.w800,
        color: _textColor,
        letterSpacing: -0.3,
      ),
      textAlign: TextAlign.center,
    );
  }
}

/// 설명 텍스트
class _DescriptionText extends StatelessWidget {
  final String text;

  const _DescriptionText({required this.text});

  static const _textColor = Color(0xFF0B1220);

  @override
  Widget build(BuildContext context) {
    return Text(
      text,
      style: TextStyle(
        fontSize: 14,
        height: 1.6,
        color: _textColor.withOpacity(0.7),
      ),
      textAlign: TextAlign.center,
    );
  }
}