//최종 완성본(결과 화면 보여줌)
import 'package:flutter/material.dart';
import 'package:get/get.dart';

import 'result_controller.dart';
import 'states/result_success_view.dart';
import 'states/result_empty_view.dart';
import 'states/result_loading_view.dart';
import 'states/result_error_view.dart';

class ResultScreen extends StatelessWidget {
  const ResultScreen({super.key});

  @override
  Widget build(BuildContext context) {
    // ✅ 이미 있으면 재사용, 없으면 생성
    final c = Get.isRegistered<ResultController>()
        ? Get.find<ResultController>()
        : Get.put(ResultController());

    // ✅ Get.arguments로 사용자 입력값 받아오기
    final args = Get.arguments as Map<String, dynamic>?;
    if (args != null && args['input'] != null) {
      c.userQuery.value = args['input'] as String;
    }

    // ✅ 상태에 따라 다른 뷰 표시
    return Obx(() {
      switch (c.resultState.value) {
        case ResultState.loading:
          return const ResultLoadingView();
        case ResultState.success:
          return const ResultSuccessView();
        case ResultState.empty:
          return const ResultEmptyView();
        case ResultState.error:
          return const ResultErrorView();
      }
    });
  }
}

//로딩 화면만 보여주는 버전
// import 'package:flutter/material.dart';
// import 'package:get/get.dart';

// import 'result_controller.dart';
// import 'states/result_loading_view.dart';

// class ResultScreen extends StatelessWidget {
//   const ResultScreen({super.key});

//   @override
//   Widget build(BuildContext context) {
//     // 컨트롤러 주입
//     Get.put(ResultController());

//     // ✅ 로딩 화면만 보여줌
//     return const ResultLoadingView();
//   }
// }
