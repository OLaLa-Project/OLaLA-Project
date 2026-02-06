import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:share_plus/share_plus.dart';
import 'package:screenshot/screenshot.dart';
import 'package:path_provider/path_provider.dart';
import 'dart:io';
import 'dart:typed_data'; // Uint8List
import 'package:flutter/foundation.dart' show kIsWeb; // Platform check
import '../models/evidence_card.dart';
import '../repository/api_verify_repository.dart';
import '../../shell/shell_controller.dart';
import '../../settings/settings_screen.dart';
import '../../history/history_screen.dart';
import '../../history/history_controller.dart';
import '../../history/models/history_item.dart';
import '../../bookmark/bookmark_controller.dart';
import '../../bookmark/models/bookmark_item.dart';
import '../../bookmark/bookmark_screen.dart';
import 'widgets/shareable_result_card.dart';

enum VerdictType { trueClaim, falseClaim, mixed, unverified }

enum ResultState { loading, success, empty, error }

class ResultController extends GetxController {
  static const Size _shareImageSize = Size(800, 1400);
  static const Duration _shareRenderDelay = Duration(seconds: 1);

  // ─────────────────────────────────────────
  // Result State
  // ─────────────────────────────────────────
  final resultState = ResultState.error.obs;

  // ─────────────────────────────────────────
  // Loading UI
  // ─────────────────────────────────────────
  final loadingHeadline = '검증 중이에요'.obs;
  final loadingSubtext = '근거를 수집하고 있어요.'.obs;
  final loadingStep = 0.obs;
  
  /// Current pipeline stage (for real-time progress)
  final currentStage = 'initializing'.obs;
  final completedStages = <String>[].obs;

  // ─────────────────────────────────────────
  // Success UI (브랜드 결과 화면)
  // ─────────────────────────────────────────
  final verdictType = VerdictType.unverified.obs;

  /// 0.0 ~ 1.0 (confidence bar)
  final confidence = 0.72.obs;

  /// 결과 헤드라인(예: "대체로 사실이에요")
  final successHeadline = '검증 결과'.obs;

  /// 결과 요약/이유
  final successReason = '수집된 근거를 바탕으로 판단했어요.\n아래 근거 카드에서 출처를 직접 확인해 주세요.'.obs;

  /// 사용자의 원본 질문
  final userQuery = ''.obs;

  /// 근거 카드 리스트
  final RxList<EvidenceCard> evidenceCards = <EvidenceCard>[].obs;

  // ─────────────────────────────────────────
  // UX Actions (프로젝트 라우팅에 맞춰 구현)
  // ─────────────────────────────────────────
  bool get canCancelVerification => true;
  void cancelVerification() => Get.back();

  void openSettings() {
    Get.to(() => const SettingsScreen());
  }

  void goHistory() {
    // ✅ 실무 패턴: 결과 화면 유지하고 히스토리 화면을 push
    // 뒤로가기 시 결과 화면으로 돌아옴
    Get.to(() => const HistoryScreen());
  }

  void goHome() {
    // 홈으로 이동: 결과 화면 닫고 홈 탭으로
    Get.back();
    if (Get.isRegistered<ShellController>()) {
      Get.find<ShellController>().setTab(1);
    }
  }

  void goBookmark() {
    // ✅ 실무 패턴: 결과 화면 유지하고 북마크 화면을 push
    // 뒤로가기 시 결과 화면으로 돌아옴
    Get.to(() => const BookmarkScreen());
  }

  void addBookmark() {
    final bookmarkController = Get.isRegistered<BookmarkController>()
        ? Get.find<BookmarkController>()
        : Get.put(BookmarkController());

    final headline = successHeadline.value.isNotEmpty
        ? successHeadline.value
        : _defaultHeadline(verdictType.value);

    final item = BookmarkItem(
      id: 'r_${DateTime.now().millisecondsSinceEpoch}',
      inputSummary: headline,
      resultLabel: _bookmarkLabel(verdictType.value),
      timestamp: DateTime.now(),
    );

    bookmarkController.items.insert(0, item);

    Get.showSnackbar(
      GetSnackBar(
        message: '북마크에 추가했어요',
        duration: const Duration(seconds: 2),
        backgroundColor: Colors.black.withOpacity( 0.8),
      ),
    );
  }

  /// ✅ 이미지 생성 + 공유 (빅테크 방식)
  // ✅ 이미지 생성 + 공유 (빅테크 방식)
  /// ✅ 이미지 생성 + 공유 (Cross-Platform Support)
  Future<void> shareResult() async {
    try {
      debugPrint('📝 공유 프로세스 시작...');

      // 1) 이미지 생성 (Uint8List Bytes)
      debugPrint('🎨 이미지 생성 (캡처) 시작...');
      final imageBytes = await _captureShareImage();
      
      if (imageBytes.isEmpty) {
        throw StateError('이미지 생성 실패: 데이터 없음');
      }
      debugPrint('✅ 이미지 캡처 완료: ${imageBytes.lengthInBytes} bytes');

      // 2) 공유 실행 (플랫폼 분기)
      debugPrint('📤 공유 시트 열기...');

      // ✅ iPad/iOS용 공유 위치 설정
      final box = Get.context?.findRenderObject() as RenderBox?;
      final screenSize = box?.size ?? const Size(390, 844);
      final shareButtonRect = Rect.fromLTWH(
        screenSize.width - 74,
        screenSize.height - 142,
        56,
        56,
      );

      final XFile xFile;
      
      // 🌐 WEB: 파일 시스템 접근 불가 -> 메모리(Bytes)에서 바로 생성
      if (kIsWeb) {
        debugPrint('🌐 Web 환경 감지: 메모리 공유 방식장 사용');
        xFile = XFile.fromData(
          imageBytes, 
          mimeType: 'image/png', 
          name: 'olala_result.png'
        );
      } 
      // 📱 APP: 파일 시스템 사용 (기존 방식)
      else {
        debugPrint('📱 App 환경 감지: 파일 시스템 방식 사용');
        final directory = await getTemporaryDirectory();
        final imagePath = '${directory.path}/olala_result_${DateTime.now().millisecondsSinceEpoch}.png';
        final file = File(imagePath);
        await file.writeAsBytes(imageBytes);
        xFile = XFile(imagePath);
      }

      final result = await Share.shareXFiles(
        [xFile],
        subject: 'OLaLA 팩트체크 결과',
        sharePositionOrigin: shareButtonRect,
      );

      // 3) 공유 결과 처리
      debugPrint('✅ 공유 완료: ${result.status}');
    } catch (e, stackTrace) {
      debugPrint('❌ 공유 실패: $e');
      debugPrint('스택 트레이스: $stackTrace');
    }
  }

  /// 공유용 이미지 데이터(Bytes) 생성
  Future<Uint8List> _captureShareImage() async {
    final screenshotController = ScreenshotController();
    final context = Get.context;
    const pixelRatio = 2.0;
    
    // View context fallback for headless/background execution
    final fallBackView = WidgetsBinding.instance.platformDispatcher.views.first;
    final view = context != null
        ? (View.maybeOf(context) ?? fallBackView)
        : fallBackView;
        
    final baseMedia = MediaQueryData.fromView(view);
    final shareMedia = baseMedia.copyWith(
      size: _shareImageSize,
      devicePixelRatio: pixelRatio,
    );

    return await screenshotController.captureFromWidget(
      MediaQuery(
        data: shareMedia,
        child: Align(
          alignment: Alignment.topCenter,
          child: SizedBox(
            width: _shareImageSize.width,
            child: ShareableResultCard(
              verdict: verdictType.value,
              headline: successHeadline.value.isNotEmpty
                  ? successHeadline.value
                  : _defaultHeadline(verdictType.value),
              confidence: confidence.value.clamp(0.0, 1.0),
              reason: successReason.value,
              evidenceCount: evidenceCards.length,
              userQuery: userQuery.value,
              evidenceCards: evidenceCards.toList(),
            ),
          ),
        ),
      ),
      context: context,
      targetSize: _shareImageSize,
      pixelRatio: pixelRatio,
      delay: _shareRenderDelay,
    );
  }



  String _defaultHeadline(VerdictType v) {
    switch (v) {
      case VerdictType.trueClaim:
        return '대체로 사실이에요';
      case VerdictType.falseClaim:
        return '사실과 달라요';
      case VerdictType.mixed:
        return '일부만 사실이에요';
      case VerdictType.unverified:
        return '판단하기 어려워요';
    }
  }

  String _bookmarkLabel(VerdictType v) {
    switch (v) {
      case VerdictType.trueClaim:
        return 'TRUE';
      case VerdictType.falseClaim:
        return 'FALSE';
      case VerdictType.mixed:
        return 'MIXED';
      case VerdictType.unverified:
        return 'UNVERIFIED';
    }
  }

  final ApiVerifyRepository _repository = ApiVerifyRepository();

  @override
  void onInit() {
    super.onInit();
    final args = Get.arguments as Map<String, dynamic>?;
    if (args != null && args['input'] != null) {
      userQuery.value = args['input'] as String;
      final mode = args['mode'] as String? ?? 'text';
      startVerification(userQuery.value, mode);
    }
  }

  Future<void> startVerification(String input, String mode) async {
    debugPrint('🚀 Starting verification: input=$input, mode=$mode');
    resultState.value = ResultState.loading;
    loadingHeadline.value = '검증 중이에요';
    currentStage.value = 'initializing';
    completedStages.clear();
    
    try {
      debugPrint('📡 Getting stream from repository...');
      final stream = _repository.verifyTruthStream(input: input, inputType: mode);
      
      debugPrint('🎧 Listening to stream...');
      await for (final event in stream) {
        debugPrint('📨 Received event: ${event['event']}');
        final eventType = event['event'] as String?;
        
        if (eventType == 'stage_complete') {
          // Update current stage
          final stageName = event['stage'] as String? ?? 'unknown';
          debugPrint('✅ Stage complete: $stageName');
          completedStages.add(stageName);
          currentStage.value = stageName;
          
          // Update loading text based on stage
          _updateLoadingText(stageName);
          debugPrint('📊 Updated UI: headline=${loadingHeadline.value}, step=${loadingStep.value}');
          
        } else if (eventType == 'complete') {
          // Final result received
          debugPrint('🎉 Pipeline complete!');
          final data = event['data'] as Map<String, dynamic>;
          _processResult(data);
          resultState.value = ResultState.success;
          break;
          
        } else if (eventType == 'error') {
          debugPrint('❌ Stream error: ${event['data']}');
          resultState.value = ResultState.error;
          break;
        }
      }
      debugPrint('🏁 Stream ended');
    } catch (e) {
      debugPrint('💥 Verify Error: $e');
      resultState.value = ResultState.error;
    }
  }
  
  void _updateLoadingText(String stageName) {
    if (stageName.contains('normalize')) {
      loadingHeadline.value = '주장/콘텐츠 추출 중';
      loadingStep.value = 0;
    } else if (stageName.contains('stage03') || stageName.contains('wiki') || stageName.contains('web') || stageName.contains('collect')) {
      loadingHeadline.value = '관련 근거 수집 중';
      loadingStep.value = 1;
    } else if (stageName.contains('judge') || stageName.contains('aggregate')) {
      loadingHeadline.value = '근거 기반 판정 제공 중';
      loadingStep.value = 2;
    }
  }
  

  void _processResult(Map<String, dynamic> resultMap) {
    final label = resultMap['label'] as String;
    verdictType.value = _parseVerdict(label);
    confidence.value = (resultMap['confidence'] as num).toDouble();
    
    final summary = resultMap['summary'] as String?;
    successHeadline.value = (summary != null && summary.length < 50) 
        ? summary 
        : _defaultHeadline(verdictType.value);
        
    final rationaleList = (resultMap['rationale'] as List?)?.cast<String>() ?? [];
    successReason.value = rationaleList.isNotEmpty 
        ? rationaleList.join('\n') 
        : (summary ?? '분석이 완료되었습니다.');
    
    final citations = (resultMap['citations'] as List?) ?? [];
    evidenceCards.value = citations.map<EvidenceCard>((c) => EvidenceCard.fromJson(c)).toList();

    // Save to history
    _saveHistory();
  }

  void _saveHistory() {
    try {
      final historyController = Get.isRegistered<HistoryController>()
          ? Get.find<HistoryController>()
          : Get.put(HistoryController());

      final item = HistoryItem(
        id: 'h_${DateTime.now().millisecondsSinceEpoch}',
        inputSummary: successHeadline.value,
        resultLabel: _bookmarkLabel(verdictType.value),
        timestamp: DateTime.now(),
        confidence: confidence.value,
        headline: successHeadline.value,
        summary: successReason.value,
        userQuery: userQuery.value,
        evidenceCards: evidenceCards.toList(),
      );

      historyController.saveItem(item);
      debugPrint('✅ History saved: ${item.id}');
    } catch (e) {
      debugPrint('❌ Failed to save history: $e');
    }
  }

  /// Load result from history item (for viewing details)
  void loadFromHistory(HistoryItem item) {
    userQuery.value = item.userQuery;
    verdictType.value = _parseVerdict(item.resultLabel);
    confidence.value = item.confidence;
    successHeadline.value = item.headline;
    successReason.value = item.summary;
    evidenceCards.value = item.evidenceCards;
    
    // Set state to success immediately to show the result
    resultState.value = ResultState.success;
  }

  VerdictType _parseVerdict(String label) {
    switch (label.toUpperCase()) {
      case 'TRUE': return VerdictType.trueClaim;
      case 'FALSE': return VerdictType.falseClaim;
      case 'MIXED': return VerdictType.mixed;
      default: return VerdictType.unverified;
    }
  }

}

