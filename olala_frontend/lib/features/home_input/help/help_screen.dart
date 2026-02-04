import 'package:flutter/material.dart';

import 'widgets/tutorial_content.dart';

/// 도움말 화면
///
/// 앱 사용법을 단계별로 설명하는 튜토리얼 화면
class HelpScreen extends StatefulWidget {
  const HelpScreen({super.key});

  @override
  State<HelpScreen> createState() => _HelpScreenState();
}

class _HelpScreenState extends State<HelpScreen> {
  final PageController _pageController = PageController();
  int _currentPage = 0;

  static const _primaryColor = Color(0xFF87CEEB);
  static const _primaryDark = Color(0xFF5DADE2);
  static const _textColor = Color(0xFF0B1220);

  @override
  void dispose() {
    _pageController.dispose();
    super.dispose();
  }

  void _goToPage(int page) {
    _pageController.animateToPage(
      page,
      duration: const Duration(milliseconds: 300),
      curve: Curves.easeInOut,
    );
  }

  void _nextPage() {
    if (_currentPage < TutorialContent.totalSteps - 1) {
      _goToPage(_currentPage + 1);
    }
  }

  void _previousPage() {
    if (_currentPage > 0) {
      _goToPage(_currentPage - 1);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: _buildAppBar(),
      body: Column(
        children: [
          Expanded(child: _buildPageView()),
          _buildNavigationButtons(),
        ],
      ),
    );
  }

  PreferredSizeWidget _buildAppBar() {
    return AppBar(
      backgroundColor: Colors.white,
      elevation: 0,
      leading: IconButton(
        icon: const Icon(Icons.close, color: _textColor),
        onPressed: () => Navigator.of(context).pop(),
      ),
      title: const Text(
        '사용 가이드',
        style: TextStyle(
          color: _textColor,
          fontWeight: FontWeight.w700,
          fontSize: 18,
        ),
      ),
      centerTitle: true,
    );
  }

  Widget _buildPageView() {
    return PageView.builder(
      controller: _pageController,
      onPageChanged: (page) => setState(() => _currentPage = page),
      itemCount: TutorialContent.totalSteps,
      itemBuilder: (context, index) {
        final step = TutorialContent.steps[index];
        return Center(
          child: TutorialCard(
            step: step,
            stepNumber: index + 1,
            totalSteps: TutorialContent.totalSteps,
          ),
        );
      },
    );
  }

  Widget _buildNavigationButtons() {
    final isFirstPage = _currentPage == 0;
    final isLastPage = _currentPage == TutorialContent.totalSteps - 1;

    return SafeArea(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            // 이전 버튼
            if (!isFirstPage)
              _SecondaryButton(text: '이전', onPressed: _previousPage)
            else
              const SizedBox(width: 80),

            const Spacer(),

            // 다음/완료 버튼
            _PrimaryButton(
              text: isLastPage ? '완료' : '다음',
              onPressed: isLastPage ? () => Navigator.of(context).pop() : _nextPage,
            ),
          ],
        ),
      ),
    );
  }
}

/// 주요 액션 버튼
class _PrimaryButton extends StatelessWidget {
  final String text;
  final VoidCallback onPressed;

  const _PrimaryButton({required this.text, required this.onPressed});

  static const _primaryColor = Color(0xFF87CEEB);
  static const _primaryDark = Color(0xFF5DADE2);

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [_primaryColor, _primaryDark],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: _primaryColor.withOpacity(0.25),
            blurRadius: 10,
            offset: const Offset(0, 3),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onPressed,
          borderRadius: BorderRadius.circular(28),
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 12),
            child: Text(
              text,
              style: const TextStyle(
                fontSize: 15,
                fontWeight: FontWeight.w900,
                color: Colors.white,
                letterSpacing: -0.3,
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// 보조 액션 버튼
class _SecondaryButton extends StatelessWidget {
  final String text;
  final VoidCallback onPressed;

  const _SecondaryButton({required this.text, required this.onPressed});

  static const _textColor = Color(0xFF0B1220);

  @override
  Widget build(BuildContext context) {
    return TextButton(
      onPressed: onPressed,
      style: TextButton.styleFrom(
        foregroundColor: _textColor.withOpacity(0.65),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      ),
      child: Text(
        text,
        style: const TextStyle(
          fontWeight: FontWeight.w600,
          fontSize: 15,
        ),
      ),
    );
  }
}