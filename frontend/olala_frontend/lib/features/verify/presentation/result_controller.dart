import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:share_plus/share_plus.dart';
import 'package:screenshot/screenshot.dart';
import 'package:path_provider/path_provider.dart';
import 'dart:io';
import '../models/evidence_card.dart';
import '../models/verification_request.dart';
import '../repository/verify_repository.dart';
import '../repository/mock_verify_repository.dart';
import '../../shell/shell_controller.dart';
import '../../settings/settings_screen.dart';
import '../../history/history_screen.dart';
import '../../bookmark/bookmark_controller.dart';
import '../../bookmark/models/bookmark_item.dart';
import '../../bookmark/bookmark_screen.dart';
import 'widgets/shareable_result_card.dart';

enum VerdictType { trueClaim, falseClaim, mixed, unverified }

enum ResultState { loading, success, empty, error }

class ResultController extends GetxController {
  // ─────────────────────────────────────────
  // Repository (FastAPI 백엔드 연동 준비)
  // ─────────────────────────────────────────
  late final VerifyRepository _repository;

  ResultController({VerifyRepository? repository})
      : _repository = repository ?? MockVerifyRepository();
  static const double _shareImageShortSide = 1080;
  static const Duration _shareRenderDelay = Duration(seconds: 1);

  // ─────────────────────────────────────────
  // Result State
  // ─────────────────────────────────────────
  final resultState = ResultState.loading.obs;

  // ─────────────────────────────────────────
  // Loading UI
  // ─────────────────────────────────────────
  final loadingHeadline = '검증 중이에요'.obs;
  final loadingSubtext = '근거를 수집하고 있어요.'.obs;
  final loadingStep = 0.obs;

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
  // Verification Logic
  // ─────────────────────────────────────────

  /// 검증 시작 (백엔드 API 호출)
  Future<void> startVerification(String input) async {
    if (input.isEmpty) {
      resultState.value = ResultState.empty;
      return;
    }

    try {
      // ✅ 로딩 상태로 전환
      resultState.value = ResultState.loading;
      userQuery.value = input;

      // ✅ 검증 요청 생성
      final request = VerificationRequest.fromInput(input);

      // ✅ Repository를 통해 검증 (단계별 진행 콜백)
      final result = await _repository.verify(
        request,
        onProgress: (step, message) {
          // 단계별 업데이트
          loadingStep.value = step;

          // 메시지 업데이트 (선택)
          switch (step) {
            case 0:
              loadingHeadline.value = '주장을 분석하고 있어요';
              loadingSubtext.value = 'URL이나 문장에서 핵심을 추출하고 있어요.';
              break;
            case 1:
              loadingHeadline.value = '관련 근거를 찾고 있어요';
              loadingSubtext.value = '신뢰할 수 있는 출처와 기사를 수집 중이에요.';
              break;
            case 2:
              loadingHeadline.value = '최종 판단을 만들고 있어요';
              loadingSubtext.value = '근거를 바탕으로 결과를 생성하고 있어요.';
              break;
          }
        },
      );

      // ✅ 결과 데이터 반영
      verdictType.value = _parseVerdictType(result.verdict);
      confidence.value = result.confidence;
      successHeadline.value = result.headline;
      successReason.value = result.reason;
      evidenceCards.value = result.evidenceCards;

      // ✅ 성공 상태로 전환
      resultState.value = ResultState.success;
    } catch (e) {
      debugPrint('❌ 검증 실패: $e');
      resultState.value = ResultState.error;
    }
  }

  /// verdict 문자열을 VerdictType으로 변환
  VerdictType _parseVerdictType(String verdict) {
    switch (verdict.toLowerCase()) {
      case 'true':
        return VerdictType.trueClaim;
      case 'false':
        return VerdictType.falseClaim;
      case 'mixed':
        return VerdictType.mixed;
      default:
        return VerdictType.unverified;
    }
  }

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
        backgroundColor: Colors.black.withValues(alpha: 0.8),
      ),
    );
  }

  /// ✅ 이미지 생성 + 공유 (빅테크 방식)
  Future<void> shareResult() async {
    try {
      debugPrint('📝 공유 프로세스 시작...');

      // 1) 이미지 생성
      debugPrint('🎨 이미지 생성 시작...');
      final imageFile = await _generateShareImage();
      debugPrint('✅ 이미지 생성 완료: ${imageFile.path}');

      // 2) 공유 실행
      debugPrint('📤 공유 시트 열기...');

      // ✅ iPad/iOS용 공유 위치 설정 (공유 버튼 위치: 우하단)
      final box = Get.context?.findRenderObject() as RenderBox?;
      final screenSize = box?.size ?? const Size(390, 844);

      final shareButtonRect = Rect.fromLTWH(
        screenSize.width - 74,
        screenSize.height - 142,
        56,
        56,
      );

      final result = await Share.shareXFiles(
        [XFile(imageFile.path)],
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

  /// 공유용 이미지 생성 (스크린샷)
  Future<File> _generateShareImage() async {
    final screenshotController = ScreenshotController();
    final context = Get.context;
    const pixelRatio = 2.0;
    final fallBackView = WidgetsBinding.instance.platformDispatcher.views.first;
    final view = context != null
        ? (View.maybeOf(context) ?? fallBackView)
        : fallBackView;
    final baseMedia = MediaQueryData.fromView(view);
    final shareImageSize = _resolveShareImageSize(baseMedia.size);
    final shareMedia = baseMedia.copyWith(
      size: shareImageSize,
      devicePixelRatio: pixelRatio,
    );

    final image = await screenshotController.captureFromWidget(
      MediaQuery(
        data: shareMedia,
        child: Align(
          alignment: Alignment.topCenter,
          child: SizedBox(
            width: shareImageSize.width,
            height: shareImageSize.height,
            child: ShareableResultCard(
              imageSize: shareImageSize,
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
      targetSize: shareImageSize,
      pixelRatio: pixelRatio,
      delay: _shareRenderDelay,
    );

    if (image.isEmpty) {
      throw StateError('공유 이미지 생성 실패: 빈 이미지');
    }

    // 임시 디렉토리에 저장
    final directory = await getTemporaryDirectory();
    final imagePath =
        '${directory.path}/olala_result_${DateTime.now().millisecondsSinceEpoch}.png';
    final imageFile = File(imagePath);

    await imageFile.writeAsBytes(image);
    return imageFile;
  }

  Size _resolveShareImageSize(Size screenSize) {
    final safeWidth = screenSize.width > 0 ? screenSize.width : 390;
    final safeHeight = screenSize.height > 0 ? screenSize.height : 844;
    final shortSide = safeWidth < safeHeight ? safeWidth : safeHeight;
    final longSide = safeWidth < safeHeight ? safeHeight : safeWidth;
    final aspectRatio = shortSide / longSide;
    final height = (_shareImageShortSide / aspectRatio).roundToDouble();
    return Size(_shareImageShortSide, height);
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

}
