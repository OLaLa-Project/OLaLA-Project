import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../result_controller.dart';
import '../widgets/progress_panel.dart';

class ResultLoadingView extends GetView<ResultController> {
  const ResultLoadingView({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    // ✅ 첨부 이미지와 유사한 블루 배경 (프로젝트 ColorToken 있으면 교체)
    const bg = Color(0xFF5A88FF);

    return Scaffold(
      backgroundColor: bg,
      body: SafeArea(
        top: true,
        bottom: true,
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20),
          child: Column(
            children: [
              const SizedBox(height: 22),

              Expanded(
                child: Center(
                  child: ConstrainedBox(
                    constraints: const BoxConstraints(maxWidth: 520),
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        const _SpinnerBadge(),
                        const SizedBox(height: 18),

                        // ✅ 헤드라인
                        Obx(() {
                          final text =
                              controller.loadingHeadline.value.isNotEmpty
                                  ? controller.loadingHeadline.value
                                  : 'OLaLA로 검증하고 있어요';
                          return Text(
                            text,
                            textAlign: TextAlign.center,
                            style: theme.textTheme.headlineSmall?.copyWith(
                              color: Colors.white,
                              fontWeight: FontWeight.w800,
                              height: 1.15,
                            ),
                          );
                        }),
                        const SizedBox(height: 10),

                        // ✅ 서브텍스트
                        Obx(() {
                          final text =
                              controller.loadingSubtext.value.isNotEmpty
                                  ? controller.loadingSubtext.value
                                  : 'URL 또는 문장을 분석해\n근거와 함께 결과를 만들고 있어요.';
                          return Text(
                            text,
                            textAlign: TextAlign.center,
                            style: theme.textTheme.bodyMedium?.copyWith(
                              color: Colors.white.withOpacity(0.82),
                              height: 1.45,
                              fontWeight: FontWeight.w500,
                            ),
                          );
                        }),
                        const SizedBox(height: 18),

                        // ✅ 단계 패널 (1/2/3)
                        Obx(() {
                          final step = controller.loadingStep.value; // 0~2
                          final step1 = controller.step1Detail.value.isNotEmpty
                              ? controller.step1Detail.value
                              : 'URL이나 문장에서 핵심을 가져옵니다.';
                          final step2 = controller.step2Detail.value.isNotEmpty
                              ? controller.step2Detail.value
                              : '관련 기사와 출처를 찾습니다.';
                          final step3 = controller.step3Detail.value.isNotEmpty
                              ? controller.step3Detail.value
                              : '판단과 함께 근거를 보여줍니다.';
                          return ProgressPanel(
                            currentStep: step,
                            steps: [
                              ProgressStep(
                                indexLabel: '1',
                                title: '주장/콘텐츠 추출',
                                description: step1,
                              ),
                              ProgressStep(
                                indexLabel: '2',
                                title: '관련 근거 수집',
                                description: step2,
                              ),
                              ProgressStep(
                                indexLabel: '3',
                                title: '근거 기반 판단 제공',
                                description: step3,
                              ),
                            ],
                          );
                        }),

                        const SizedBox(height: 14),
                        Text(
                          '※ 결과는 참고용이며, 신뢰도/근거를 함께 확인하세요.',
                          textAlign: TextAlign.center,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: Colors.white.withOpacity(0.75),
                            height: 1.35,
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),

              // ✅ 하단 Cancel 버튼
              SizedBox(
                width: double.infinity,
                height: 58,
                child: ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: Colors.white,
                    foregroundColor: Colors.black87,
                    elevation: 0,
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(18),
                    ),
                  ),
                  onPressed: () {
                    // 컨트롤러가 취소 지원하면 취소, 아니면 back
                    if (controller.canCancelVerification) {
                      controller.cancelVerification();
                    } else {
                      Get.back();
                    }
                  },
                  child: Text(
                    '취소',
                    style: theme.textTheme.titleMedium?.copyWith(
                      fontWeight: FontWeight.w800,
                    ),
                  ),
                ),
              ),

              const SizedBox(height: 10),
            ],
          ),
        ),
      ),
    );
  }
}

/// 상단 스피너 배지(첨부 이미지 톤에 맞춘 "글로우+카드" 느낌)
class _SpinnerBadge extends StatelessWidget {
  const _SpinnerBadge();

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 92,
      height: 92,
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.14),
        borderRadius: BorderRadius.circular(28),
        border: Border.all(color: Colors.white.withOpacity(0.18), width: 1),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.12),
            blurRadius: 22,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      alignment: Alignment.center,
      child: SizedBox(
        width: 34,
        height: 34,
        child: Stack(
          alignment: Alignment.center,
          children: [
            // 링(배경)
            SizedBox(
              width: 34,
              height: 34,
              child: CircularProgressIndicator(
                value: 1,
                strokeWidth: 4,
                valueColor: AlwaysStoppedAnimation(
                  Colors.white.withOpacity(0.22),
                ),
              ),
            ),
            // 스피너(전경)
            SizedBox(
              width: 34,
              height: 34,
              child: CircularProgressIndicator(
                strokeWidth: 4,
                valueColor: AlwaysStoppedAnimation(
                  Colors.white.withOpacity(0.95),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
