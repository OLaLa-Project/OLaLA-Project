import 'package:flutter/widgets.dart';
import 'package:get/get.dart';

import '../../app/routes.dart';
import '../../shared/storage/local_storage.dart';

/// OLaLA Coach Controller
///
/// 현업 기준 정리 포인트:
/// - totalSteps 하드코딩 제거(외부에서 주입 가능)
/// - PageView와 상태를 단일 소스로 동기화
/// - complete/skip 중복 제거
class CoachController extends GetxController {
  /// 총 단계 수 (기본 3)
  final int totalSteps;

  CoachController({this.totalSteps = 3});

  /// 현재 단계 (1-based)
  final RxInt currentStep = 1.obs;

  late final PageController pageController;

  @override
  void onInit() {
    super.onInit();
    pageController = PageController(initialPage: 0);
  }

  @override
  void onClose() {
    pageController.dispose();
    super.onClose();
  }

  /// PageView onPageChanged와 연결 (0-based index)
  void syncFromPageIndex(int pageIndex) {
    final step = (pageIndex + 1).clamp(1, totalSteps);
    if (currentStep.value != step) currentStep.value = step;
  }

  /// 다음 단계로 이동
  void nextStep() {
    final next = (currentStep.value + 1).clamp(1, totalSteps);
    if (next == currentStep.value) return;
    _goToStep(next);
  }

  /// 이전 단계로 이동
  void previousStep() {
    final prev = (currentStep.value - 1).clamp(1, totalSteps);
    if (prev == currentStep.value) return;
    _goToStep(prev);
  }

  void _goToStep(int step) {
    currentStep.value = step;
    final pageIndex = step - 1;

    // PageController가 아직 attach되지 않은 경우(빌드 전)에도 안전하게 처리
    if (!pageController.hasClients) return;

    pageController.animateToPage(
      pageIndex,
      duration: const Duration(milliseconds: 280),
      curve: Curves.easeOutCubic,
    );
  }

  Future<void> completeCoach() => _finishCoach(reason: _FinishReason.completed);

  Future<void> skipCoach() => _finishCoach(reason: _FinishReason.skipped);

  Future<void> _finishCoach({required _FinishReason reason}) async {
    // TODO: reason에 따라 analytics 이벤트를 분기할 수 있음
    await LocalStorage.setCoachCompleted();
    await LocalStorage.setFirstLaunchCompleted();
    Get.offAllNamed(AppRoutes.shell);
  }
}

enum _FinishReason { completed, skipped }

