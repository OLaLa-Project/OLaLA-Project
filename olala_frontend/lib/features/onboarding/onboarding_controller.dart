import 'package:get/get.dart';
import '../../app/routes.dart';
import '../../shared/storage/local_storage.dart';

class OnboardingController extends GetxController {
  bool _navigating = false;

  /// ✅ 시작하기 버튼: Shell로 이동 (Coach는 HomeInput에서 자동 표시)
  Future<void> onTapStart() async {
    if (_navigating) return;
    _navigating = true;

    await LocalStorage.setOnboardingCompleted();

    // 라우트 레이스/중복 이동 방지
    if (Get.currentRoute == AppRoutes.onboarding) {
      Get.offAllNamed(AppRoutes.shell);
    }
  }

  void onTapTerms() {
    Get.snackbar('이용약관', '이용약관 화면/링크는 추후 연결됩니다.');
  }

  void onTapPrivacy() {
    Get.snackbar('개인정보처리방침', '개인정보처리방침 화면/링크는 추후 연결됩니다.');
  }
}
