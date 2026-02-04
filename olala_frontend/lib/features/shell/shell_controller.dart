import 'package:get/get.dart';
import '../home_input/home_input_controller.dart';

class ShellController extends GetxController {
  final tabIndex = 1.obs; // ✅ 기본은 홈(1)

  void setTab(int i) {
    // 홈 탭을 다시 누르면 새로고침
    if (i == 1 && tabIndex.value == 1) {
      if (Get.isRegistered<HomeInputController>()) {
        Get.find<HomeInputController>().refreshHome();
      }
    }
    tabIndex.value = i;
  }
}
