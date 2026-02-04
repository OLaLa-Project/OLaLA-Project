import 'package:get/get.dart';
import 'package:flutter/material.dart';
import '../../../../data/provider/api_client.dart';
import '../../../../shared/services/truth_check_service.dart';

class StageLog {
  final String stage;
  final String label;
  final Map<String, dynamic> data;
  final DateTime timestamp;
  
  StageLog({
    required this.stage, 
    required this.label, 
    this.data = const {},
    DateTime? timestamp,
  }) : timestamp = timestamp ?? DateTime.now();
}

class ResultController extends GetxController {
  final TruthCheckService _truthCheckService = TruthCheckService();

  // State
  RxList<StageLog> logs = <StageLog>[].obs;
  Rx<TruthCheckResponse?> finalResult = Rx<TruthCheckResponse?>(null);
  RxBool isLoading = true.obs;
  RxString currentStage = ''.obs;

  @override
  void onInit() {
    super.onInit();
    final args = Get.arguments;
    if (args != null && args is TruthCheckRequest) {
      _startVerification(args);
    } else if (args != null && args is TruthCheckResponse) {
      finalResult.value = args;
      isLoading.value = false;
    } else {
      Get.snackbar('오류', '검증 요청 정보가 없습니다.');
      isLoading.value = false;
    }
  }

  void _startVerification(TruthCheckRequest request) {
    isLoading.value = true;
    logs.clear();
    _addLog('initializing', '검증을 시작합니다...', {});

    _truthCheckService.checkTruthStream(request).listen(
      (event) {
        final eventType = event['event'];
        
        if (eventType == 'stage_complete') {
          final stage = event['stage'];
          final data = event['data'] as Map<String, dynamic>? ?? {};
          currentStage.value = stage;
          
          final label = _mapStageToKor(stage);
          _addLog(stage, label, data);
        } 
        else if (eventType == 'complete') {
          final data = event['data'];
          if (data != null) {
            finalResult.value = TruthCheckResponse.fromJson(data);
             _addLog('complete', '검증이 완료되었습니다.', {});
          }
          isLoading.value = false;
        } 
        else if (eventType == 'error') {
          final msg = event['data']['display_message'] ?? '알 수 없는 오류';
           _addLog('error', '오류 발생: $msg', event['data'] ?? {});
          Get.snackbar('오류', msg, backgroundColor: Colors.redAccent, colorText: Colors.white);
          isLoading.value = false;
        }
      },
      onError: (e) {
         _addLog('error', '통신 오류: $e', {});
        isLoading.value = false;
      },
    );
  }

  void _addLog(String stage, String label, Map<String, dynamic> data) {
    logs.add(StageLog(stage: stage, label: label, data: data));
    // Auto scroll logic handled by listview usually
  }

  String _mapStageToKor(String stage) {
    switch (stage) {
      case 'stage01_normalize': return '1. 입력 내용 분석';
      case 'stage02_querygen': return '2. 검색 검색어 생성';
      case 'stage03_web': return '3. 웹 검색 수행';
      case 'stage03_wiki': return '3. 위키 백과 검색';
      case 'stage03_merge': return '3. 검색 결과 취합';
      case 'stage04_score': return '4. 신뢰도 평가';
      case 'stage05_topk': return '5. 핵심 증거 선별';
      case 'stage06_verify_support': return '6. 지지 관점 검증';
      case 'stage07_verify_skeptic': return '7. 반박 관점 검증';
      case 'stage08_aggregate': return '8. 결과 종합';
      case 'stage09_judge': return '9. 최종 판정';
      case 'complete': return '완료';
      default: return stage;
    }
  }

  void goBack() {
    Get.back();
  }
}
