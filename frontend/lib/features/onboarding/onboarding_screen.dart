import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'onboarding_controller.dart';

class OnboardingScreen extends StatelessWidget {
  const OnboardingScreen({super.key});

  static const Color _bgColor = Color(0xFF5A87FF);
  static const Color _inkColor = Color(0xFF1F2A37);
  static const String _logoAsset = 'assets/images/brand_logo.png';

  static const EdgeInsets _hPadding = EdgeInsets.symmetric(horizontal: 24);
  static const EdgeInsets _bottomAreaPadding = EdgeInsets.fromLTRB(24, 0, 24, 18);

  @override
  Widget build(BuildContext context) {
    // ✅ build()에서 매번 lazyPut 하지 않도록(리빌드/핫리로드 대비)
    final c = Get.isRegistered<OnboardingController>()
        ? Get.find<OnboardingController>()
        : Get.put(OnboardingController());

    final textTheme = Theme.of(context).textTheme;

    return Scaffold(
      backgroundColor: _bgColor,
      body: SafeArea(
        child: Column(
          children: [
            // ✅ 상단/중단 콘텐츠는 스크롤 영역
            Expanded(
              child: SingleChildScrollView(
                physics: const BouncingScrollPhysics(),
                padding: _hPadding,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.center,
                  children: [
                    const SizedBox(height: 24),

                    // Brand Logo (120x120) - UI 유지
                    Image.asset(
                      _logoAsset,
                      width: 120,
                      height: 120,
                      fit: BoxFit.contain,
                    ),

                    const SizedBox(height: 20),

                    // Headline (height: 64) - UI 유지
                    SizedBox(
                      height: 64,
                      child: Center(
                        child: Text(
                          'OLaLA로\n검증하세요',
                          textAlign: TextAlign.center,
                          style: textTheme.headlineSmall?.copyWith(
                            color: Colors.white,
                            fontWeight: FontWeight.w800,
                            height: 1.15,
                          ),
                        ),
                      ),
                    ),

                    const SizedBox(height: 8),

                    // SubText (height: 48) - UI 유지
                    SizedBox(
                      height: 48,
                      child: Center(
                        child: Text(
                          'URL 또는 문장을 넣으면\n근거와 함께 결과를 보여드려요.',
                          textAlign: TextAlign.center,
                          style: textTheme.bodyMedium?.copyWith(
                            color: Colors.white.withOpacity(0.92),
                            height: 1.2,
                          ),
                        ),
                      ),
                    ),

                    const SizedBox(height: 16),

                    // Steps - UI 유지
                    const _StepRow(
                      badgeText: '1',
                      title: '주장/콘텐츠 추출',
                      desc: 'URL이나 문장에서 핵심을 가져옵니다.',
                    ),
                    const SizedBox(height: 12),
                    const _StepRow(
                      badgeText: '2',
                      title: '관련 근거 수집',
                      desc: '관련 기사와 출처를 찾습니다.',
                    ),
                    const SizedBox(height: 12),
                    const _StepRow(
                      badgeText: '3',
                      title: '근거 기반 판단 제공',
                      desc: '판단과 함께 근거를 보여줍니다.',
                    ),

                    const SizedBox(height: 18),

                    // Trust Notice (height: 40) - UI 유지
                    SizedBox(
                      height: 40,
                      child: Center(
                        child: Text(
                          '※ 결과는 참고용이며, 신뢰도/근거를 함께 확인하세요.',
                          textAlign: TextAlign.center,
                          style: textTheme.bodySmall?.copyWith(
                            color: Colors.white.withOpacity(0.9),
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ),
                    ),

                    // ✅ 스크롤 영역 끝 여백(하단 고정 영역과 겹치지 않게)
                    const SizedBox(height: 24),
                  ],
                ),
              ),
            ),

            // ✅ 하단 고정 영역: 시작하기 버튼 + 약관 (UI 유지)
            Padding(
              padding: _bottomAreaPadding,
              child: Column(
                children: [
                  // Start Button (height: 56)
                  SizedBox(
                    height: 56,
                    width: double.infinity,
                    child: ElevatedButton(
                      onPressed: c.onTapStart,
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Colors.white,
                        foregroundColor: _inkColor,
                        elevation: 0,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                      ),
                      child: const Text(
                        '시작하기',
                        style: TextStyle(
                          fontSize: 18,
                          fontWeight: FontWeight.w800,
                        ),
                      ),
                    ),
                  ),

                  const SizedBox(height: 12),

                  // Terms row (height: 24)
                  SizedBox(
                    height: 24,
                    child: Center(
                      child: Wrap(
                        crossAxisAlignment: WrapCrossAlignment.center,
                        children: [
                          GestureDetector(
                            onTap: c.onTapTerms,
                            child: Text(
                              '이용약관',
                              style: textTheme.bodySmall?.copyWith(
                                color: Colors.white,
                                decoration: TextDecoration.underline,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                          Text(
                            '  ·  ',
                            style: textTheme.bodySmall?.copyWith(
                              color: Colors.white.withOpacity(0.9),
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          GestureDetector(
                            onTap: c.onTapPrivacy,
                            child: Text(
                              '개인정보처리방침',
                              style: textTheme.bodySmall?.copyWith(
                                color: Colors.white,
                                decoration: TextDecoration.underline,
                                fontWeight: FontWeight.w600,
                              ),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _StepRow extends StatelessWidget {
  final String badgeText;
  final String title;
  final String desc;

  const _StepRow({
    required this.badgeText,
    required this.title,
    required this.desc,
  });

  static const Color _inkColor = Color(0xFF1F2A37);

  @override
  Widget build(BuildContext context) {
    final textTheme = Theme.of(context).textTheme;

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.18),
        borderRadius: BorderRadius.circular(14),
        border: Border.all(color: Colors.white.withOpacity(0.25), width: 1),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          // Badge (24x24 circle)
          SizedBox(
            width: 24,
            height: 24,
            child: DecoratedBox(
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: Colors.white.withOpacity(0.9),
              ),
              child: Center(
                child: Text(
                  badgeText,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w800,
                    color: _inkColor,
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 10),

          // Title + Desc
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SizedBox(
                  height: 20,
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      title,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: textTheme.bodyMedium?.copyWith(
                        color: Colors.white,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                  ),
                ),
                const SizedBox(height: 4),
                SizedBox(
                  height: 16,
                  child: Align(
                    alignment: Alignment.centerLeft,
                    child: Text(
                      desc,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: textTheme.bodySmall?.copyWith(
                        color: Colors.white.withOpacity(0.92),
                        fontWeight: FontWeight.w600,
                      ),
                    ),
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
