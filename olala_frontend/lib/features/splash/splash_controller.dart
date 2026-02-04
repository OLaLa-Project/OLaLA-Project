import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../../app/routes.dart';
import '../../shared/storage/local_storage.dart';

class SplashController extends GetxController with GetSingleTickerProviderStateMixin {
  late final AnimationController controller;
  late final Animation<double> reveal;

  static const String logoAssetPath = 'assets/images/brand_logo.png';

  @override
  void onInit() {
    super.onInit();

    controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );

    reveal = CurvedAnimation(
      parent: controller,
      curve: Curves.easeOutCubic,
    );

    controller.forward();

    // 기존 네비게이션 흐름 유지 (필요 시간만 확보)
    Future.delayed(const Duration(milliseconds: 1400), () async {
      if (Get.currentRoute == AppRoutes.splash) {
        await _navigateToNextScreen();
      }
    });
  }

  @override
  void onReady() {
    super.onReady();

    // 스플래시에서 "툭" 끊기는 느낌(jank) 방지: 로고 이미지 선 디코딩
    final ctx = Get.context;
    if (ctx != null) {
      precacheImage(const AssetImage(logoAssetPath), ctx);
    }
  }

  Future<void> _navigateToNextScreen() async {
    final isFirstLaunch = await LocalStorage.isFirstLaunch();

    if (isFirstLaunch) {
      Get.offAllNamed(AppRoutes.onboarding);
    } else {
      Get.offAllNamed(AppRoutes.shell);
    }
  }

  @override
  void onClose() {
    controller.dispose();
    super.onClose();
  }
}
