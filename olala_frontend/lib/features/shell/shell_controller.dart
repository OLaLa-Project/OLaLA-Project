import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../home_input/home_input_controller.dart';

class ShellController extends GetxController {
  final tabIndex = 1.obs; // 기본은 홈(1)

  // BottomNav 측정용 GlobalKey
  final GlobalKey navHistoryKey = GlobalKey(debugLabel: 'nav_history');
  final GlobalKey navVerifyKey = GlobalKey(debugLabel: 'nav_verify');
  final GlobalKey navBookmarkKey = GlobalKey(debugLabel: 'nav_bookmark');

  // 측정된 Rect
  final Rxn<Rect> navHistoryRect = Rxn<Rect>();
  final Rxn<Rect> navVerifyRect = Rxn<Rect>();
  final Rxn<Rect> navBookmarkRect = Rxn<Rect>();

  void setTab(int i) {
    // 홈 탭을 다시 누르면 새로고침
    if (i == 1 && tabIndex.value == 1) {
      if (Get.isRegistered<HomeInputController>()) {
        Get.find<HomeInputController>().refreshHome();
      }
    }
    tabIndex.value = i;
  }

  void updateNavRects({
    Rect? history,
    Rect? verify,
    Rect? bookmark,
  }) {
    if (history != null) navHistoryRect.value = history;
    if (verify != null) navVerifyRect.value = verify;
    if (bookmark != null) navBookmarkRect.value = bookmark;
  }
}
