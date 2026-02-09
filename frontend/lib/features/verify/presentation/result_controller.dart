import 'dart:async';

import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:share_plus/share_plus.dart';
import 'package:screenshot/screenshot.dart';
import 'package:olala_frontend/shared/utils/share_xfile.dart';
import '../models/evidence_card.dart';
import '../models/verification_result.dart';
import '../repository/api_verify_repository.dart';
import 'stream_event_adapter.dart';
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
  static const Size _shareImageSize = Size(800, 1400);
  static const Duration _shareRenderDelay = Duration(seconds: 1);
  static const Duration _minStepHold = Duration(milliseconds: 900);
  static const Duration _streamStallThreshold = Duration(seconds: 8);
  static const Duration _streamWatchInterval = Duration(seconds: 1);
  static const String _defaultStep1Detail = 'URL이나 문장에서 핵심을 가져옵니다.';
  static const String _defaultStep2Detail = '관련 기사와 출처를 찾습니다.';
  static const String _defaultStep3Detail = '판단과 함께 근거를 보여줍니다.';

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
  final step1Detail = _defaultStep1Detail.obs;
  final step2Detail = _defaultStep2Detail.obs;
  final step3Detail = _defaultStep3Detail.obs;

  /// Current pipeline stage (for real-time progress)
  final currentStage = 'initializing'.obs;
  final completedStages = <String>[].obs;
  int _visibleUiStep = 1;
  DateTime _stepChangedAt = DateTime.now();
  DateTime _lastStreamEventAt = DateTime.now();
  bool _streamDelayedNoticeShown = false;
  Timer? _streamWatchdog;
  String _latestClaimMode = '';
  int _mergeNewsCount = 0;
  int _mergeWebCount = 0;
  int _mergeWikiCount = 0;
  int _lowQualityFilteredCount = 0;
  int _scorePassCount = 0;
  int _scoreTotalCount = 0;
  double _scorePassRate = 0.0;
  int _supportCitationCount = 0;
  int _skepticCitationCount = 0;

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
        backgroundColor: Colors.black.withOpacity(0.8),
      ),
    );
  }

  /// ✅ 이미지 생성 + 공유 (빅테크 방식)
  // ✅ 이미지 생성 + 공유 (빅테크 방식)
  Future<void> shareResult() async {
    try {
      debugPrint('📝 공유 프로세스 시작...');

      // 1) 이미지 생성
      debugPrint('🎨 이미지 생성 시작...');
      final imageFile = await _generateShareImage();
      debugPrint('✅ 이미지 생성 완료: ${imageFile.name}');

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
        [imageFile],
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
  Future<XFile> _generateShareImage() async {
    final screenshotController = ScreenshotController();
    final context = Get.context;
    const pixelRatio = 2.0;
    final fallBackView = WidgetsBinding.instance.platformDispatcher.views.first;
    final view = context != null
        ? (View.maybeOf(context) ?? fallBackView)
        : fallBackView;
    final baseMedia = MediaQueryData.fromView(view);
    final shareMedia = baseMedia.copyWith(
      size: _shareImageSize,
      devicePixelRatio: pixelRatio,
    );

    final image = await screenshotController.captureFromWidget(
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

    if (image.isEmpty) {
      throw StateError('공유 이미지 생성 실패: 빈 이미지');
    }

    return buildShareXFile(image);
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
    loadingSubtext.value = '근거를 수집하고 있어요.';
    loadingStep.value = 0;
    step1Detail.value = _defaultStep1Detail;
    step2Detail.value = _defaultStep2Detail;
    step3Detail.value = _defaultStep3Detail;
    currentStage.value = 'initializing';
    completedStages.clear();
    _visibleUiStep = 1;
    _stepChangedAt = DateTime.now();
    _lastStreamEventAt = DateTime.now();
    _streamDelayedNoticeShown = false;
    _latestClaimMode = '';
    _mergeNewsCount = 0;
    _mergeWebCount = 0;
    _mergeWikiCount = 0;
    _lowQualityFilteredCount = 0;
    _scorePassCount = 0;
    _scoreTotalCount = 0;
    _scorePassRate = 0.0;
    _supportCitationCount = 0;
    _skepticCitationCount = 0;
    bool receivedComplete = false;
    _startStreamWatchdog();

    try {
      debugPrint('📡 Getting stream from repository...');
      final stream =
          _repository.verifyTruthStream(input: input, inputType: mode);

      debugPrint('🎧 Listening to stream...');
      await for (final event in stream) {
        _markStreamSignal(event.receivedAt);
        debugPrint('📨 Received event: ${event.event}');

        switch (event.type) {
          case StreamEventType.streamOpen:
            debugPrint('🔓 Stream opened: trace=${event.traceId}');
            loadingSubtext.value = '스트림 연결 완료. 분석을 시작하고 있어요.';
            continue;
          case StreamEventType.heartbeat:
            final heartbeatStage = event.currentStage ?? event.stage;
            if (heartbeatStage != null && heartbeatStage.isNotEmpty) {
              currentStage.value = heartbeatStage;
            }
            loadingSubtext.value =
                _heartbeatSubtext(heartbeatStage, event.idleMs);
            continue;
          case StreamEventType.stepStarted:
          case StreamEventType.stepCompleted:
            await _updateLoadingFromUiStep(event.uiStep, event.uiStepTitle);
            continue;
          case StreamEventType.stageComplete:
            final stageName = event.stage ?? 'unknown';
            final stageData = event.data;
            debugPrint('✅ Stage complete: $stageName');
            completedStages.add(stageName);
            currentStage.value = stageName;

            if (!(await _updateLoadingFromUiStep(
                event.uiStep, event.uiStepTitle))) {
              _updateLoadingText(stageName);
            }
            _applyStageStatus(stageName);
            _applyStageOutputPreview(stageName, stageData);
            debugPrint(
                '📊 Updated UI: headline=${loadingHeadline.value}, step=${loadingStep.value}');
            break;
          case StreamEventType.complete:
            debugPrint('🎉 Pipeline complete!');
            receivedComplete = true;
            await _updateLoadingFromUiStep(3, '근거 기반 판단 제공');
            if (event.data.isEmpty) {
              debugPrint('❌ Complete event without payload');
              resultState.value = ResultState.error;
              break;
            }
            _processResult(event.data);
            resultState.value = ResultState.success;
            break;
          case StreamEventType.error:
            debugPrint('❌ Stream error: ${event.data}');
            resultState.value = ResultState.error;
            break;
          case StreamEventType.unknown:
            debugPrint('⚠️ Unknown stream event, skipping: ${event.event}');
            continue;
        }

        if (resultState.value != ResultState.loading) {
          break;
        }
      }
      if (resultState.value == ResultState.loading && !receivedComplete) {
        debugPrint('❌ Stream ended without complete event');
        resultState.value = ResultState.error;
      }
      debugPrint('🏁 Stream ended');
    } catch (e) {
      debugPrint('💥 Verify Error: $e');
      resultState.value = ResultState.error;
    } finally {
      _stopStreamWatchdog();
    }
  }

  Future<bool> _updateLoadingFromUiStep(
      int? uiStep, String? uiStepTitle) async {
    if (uiStep == null) {
      return false;
    }
    final targetStep = (uiStep.clamp(1, 3) as num).toInt();
    if (targetStep > _visibleUiStep) {
      final elapsed = DateTime.now().difference(_stepChangedAt);
      final remaining = _minStepHold - elapsed;
      if (remaining > Duration.zero) {
        await Future.delayed(remaining);
      }
      _visibleUiStep = targetStep;
      _stepChangedAt = DateTime.now();
    }

    loadingStep.value = _visibleUiStep - 1;

    final resolvedTitle = uiStepTitle?.trim();
    loadingHeadline.value = (resolvedTitle != null && resolvedTitle.isNotEmpty)
        ? '$resolvedTitle 중'
        : _headlineByStep(_visibleUiStep);
    loadingSubtext.value = _subtextByStep(_visibleUiStep);
    return true;
  }

  void _startStreamWatchdog() {
    _stopStreamWatchdog();
    _streamWatchdog = Timer.periodic(_streamWatchInterval, (_) {
      if (resultState.value != ResultState.loading) {
        return;
      }
      final stalledFor = DateTime.now().difference(_lastStreamEventAt);
      if (stalledFor >= _streamStallThreshold && !_streamDelayedNoticeShown) {
        loadingSubtext.value = '네트워크/서버 응답이 지연되고 있어요. 잠시만 기다려주세요.';
        _streamDelayedNoticeShown = true;
      }
    });
  }

  void _stopStreamWatchdog() {
    _streamWatchdog?.cancel();
    _streamWatchdog = null;
  }

  void _markStreamSignal(DateTime receivedAt) {
    _lastStreamEventAt = receivedAt;
    _streamDelayedNoticeShown = false;
  }

  Map<String, dynamic>? _asMap(dynamic value) {
    if (value is Map<String, dynamic>) {
      return value;
    }
    if (value is Map) {
      return Map<String, dynamic>.from(value);
    }
    return null;
  }

  int _citationCountFromPack(Map<String, dynamic>? pack) {
    if (pack == null) {
      return 0;
    }
    final citations = pack['citations'];
    if (citations is List) {
      return citations.length;
    }
    return 0;
  }

  int? _asInt(dynamic value) {
    if (value is int) {
      return value;
    }
    if (value is num) {
      return value.toInt();
    }
    if (value is String) {
      return int.tryParse(value);
    }
    return null;
  }

  double? _asDouble(dynamic value) {
    if (value is double) {
      return value;
    }
    if (value is num) {
      return value.toDouble();
    }
    if (value is String) {
      return double.tryParse(value);
    }
    return null;
  }

  String _clipText(String text, {int max = 90}) {
    final cleaned = text.trim().replaceAll('\n', ' ');
    if (cleaned.length <= max) {
      return cleaned;
    }
    return '${cleaned.substring(0, max)}...';
  }

  String _claimModeLabel(dynamic value) {
    final mode = (value?.toString().trim().toLowerCase() ?? '');
    if (mode == 'rumor') {
      return 'RUMOR';
    }
    if (mode == 'mixed') {
      return 'MIXED';
    }
    return 'FACT';
  }

  String _stanceLabel(dynamic value) {
    final raw = (value?.toString().trim().toUpperCase() ?? '');
    return raw.isEmpty ? 'UNVERIFIED' : raw;
  }

  String _formatConfidencePct(dynamic value) {
    final parsed = _asDouble(value);
    if (parsed == null) {
      return '0%';
    }
    final pct = parsed <= 1.0 ? parsed * 100.0 : parsed;
    return '${pct.clamp(0.0, 100.0).toStringAsFixed(0)}%';
  }

  String _formatTrust(double? value) {
    if (value == null) {
      return '0.00';
    }
    return value.clamp(0.0, 1.0).toStringAsFixed(2);
  }

  String _step2Summary() {
    final total = _mergeNewsCount + _mergeWebCount + _mergeWikiCount;
    final segments = <String>[
      '수집 $total건(뉴스 $_mergeNewsCount / 웹 $_mergeWebCount / 위키 $_mergeWikiCount)',
      '저품질 필터 $_lowQualityFilteredCount건',
    ];
    if (_scoreTotalCount > 0) {
      final passRateText =
          (_scorePassRate * 100).clamp(0.0, 100.0).toStringAsFixed(0);
      segments.add('점수 통과 $_scorePassCount/$_scoreTotalCount($passRateText%)');
    }
    return segments.join(' · ');
  }

  List<String> _riskFlags(dynamic value) {
    if (value is! List) {
      return const <String>[];
    }
    return value
        .whereType<String>()
        .map((flag) => flag.trim().toUpperCase())
        .where((flag) => flag.isNotEmpty)
        .toList(growable: false);
  }

  int _selectedEvidenceCount(
      Map<String, dynamic> stageData, Map<String, dynamic> finalVerdict) {
    final diagnostics = _asMap(stageData['stage09_diagnostics']);
    final fromDiag = _asInt(diagnostics?['selected_evidence_count']);
    if (fromDiag != null) {
      return fromDiag;
    }
    final selectedIds = finalVerdict['selected_evidence_ids'];
    if (selectedIds is List) {
      return selectedIds.length;
    }
    final citations = finalVerdict['citations'];
    if (citations is List) {
      return citations.length;
    }
    final summary = finalVerdict['evidence_summary'];
    if (summary is List) {
      return summary.length;
    }
    return 0;
  }

  String _representativeCitation(dynamic verdict) {
    final pack = _asMap(verdict);
    if (pack == null) {
      return '';
    }
    final citations = pack['citations'];
    if (citations is! List || citations.isEmpty) {
      return '';
    }
    final first = _asMap(citations.first);
    if (first == null) {
      return '';
    }
    final quote = (first['quote'] ?? first['snippet'] ?? first['title'] ?? '')
        .toString()
        .trim();
    if (quote.isEmpty) {
      return '';
    }
    return _clipText(quote, max: 80);
  }

  void _applyStageStatus(String stageName) {
    switch (stageName) {
      case 'stage01_normalize':
        loadingHeadline.value = '주장/콘텐츠 추출 중';
        loadingSubtext.value = '입력에서 핵심 주장과 맥락을 정리하고 있어요.';
        return;
      case 'stage02_querygen':
        loadingHeadline.value = '주장/콘텐츠 추출 중';
        loadingSubtext.value = '검증 포인트와 맥락을 정리하고 있어요.';
        return;
      case 'stage03_wiki':
        loadingHeadline.value = '관련 근거 수집 중';
        loadingSubtext.value = '위키피디아 기반 근거를 찾고 있어요.';
        return;
      case 'stage03_web':
        loadingHeadline.value = '관련 근거 수집 중';
        loadingSubtext.value = '웹/뉴스 출처에서 근거를 찾고 있어요.';
        return;
      case 'stage03_merge':
        loadingHeadline.value = '관련 근거 수집 중';
        loadingSubtext.value = '수집한 근거를 통합하고 있어요.';
        return;
      case 'stage04_score':
        loadingHeadline.value = '관련 근거 수집 중';
        loadingSubtext.value = '근거 신뢰도와 관련성을 점수화하고 있어요.';
        return;
      case 'stage05_topk':
        loadingHeadline.value = '관련 근거 수집 중';
        loadingSubtext.value = '핵심 근거를 선별하고 있어요.';
        return;
      case 'stage06_verify_support':
        loadingHeadline.value = '근거 기반 판단 제공 중';
        loadingSubtext.value = '주장을 지지하는 근거를 검증하고 있어요.';
        return;
      case 'stage07_verify_skeptic':
        loadingHeadline.value = '근거 기반 판단 제공 중';
        loadingSubtext.value = '반박/한계 근거를 함께 검증하고 있어요.';
        return;
      case 'stage08_aggregate':
        loadingHeadline.value = '근거 기반 판단 제공 중';
        loadingSubtext.value = '지지/반박 근거를 종합해 판단 초안을 만들고 있어요.';
        return;
      case 'stage09_judge':
        loadingHeadline.value = '근거 기반 판단 제공 중';
        loadingSubtext.value = '최종 판정과 요약을 생성하고 있어요.';
        return;
    }
  }

  void _applyStageOutputPreview(String stageName, dynamic stageData) {
    if (stageData is! Map<String, dynamic>) {
      return;
    }

    if (stageName == 'stage01_normalize') {
      final claim = (stageData['claim_text'] as String?)?.trim() ?? '';
      _latestClaimMode = _claimModeLabel(stageData['claim_mode']);
      if (claim.isEmpty) {
        return;
      }
      final detail = '주장: ${_clipText(claim)} · 모드: $_latestClaimMode';
      step1Detail.value = detail;
      loadingSubtext.value = detail;
      return;
    }

    if (stageName == 'stage02_querygen') {
      final modeText =
          _latestClaimMode.isNotEmpty ? ' · 모드: $_latestClaimMode' : '';
      final detail = '검증 포인트 정리 완료$modeText';
      step1Detail.value = detail;
      loadingSubtext.value = detail;
      return;
    }

    if (stageName == 'stage03_web' ||
        stageName == 'stage03_wiki' ||
        stageName == 'stage03_merge') {
      final web = stageData['web_candidates'];
      final wiki = stageData['wiki_candidates'];
      final mergeStats = _asMap(stageData['stage03_merge_stats']);
      if (web is List) {
        _mergeWebCount = web.length;
      }
      if (wiki is List) {
        _mergeWikiCount = wiki.length;
      }
      if (mergeStats != null) {
        final sourceMix = _asMap(mergeStats['source_mix']);
        if (sourceMix != null) {
          _mergeNewsCount = _asInt(sourceMix['news']) ?? _mergeNewsCount;
          _mergeWebCount = _asInt(sourceMix['web']) ?? _mergeWebCount;
          _mergeWikiCount = _asInt(sourceMix['wiki']) ?? _mergeWikiCount;
        }
        _lowQualityFilteredCount = _asInt(mergeStats['low_quality_filtered']) ??
            _lowQualityFilteredCount;
      }
      final detail = _step2Summary();
      step2Detail.value = detail;
      loadingSubtext.value = detail;
      return;
    }

    if (stageName == 'stage04_score') {
      final scoreDiagnostics = _asMap(stageData['score_diagnostics']);
      if (scoreDiagnostics != null) {
        _scorePassCount =
            _asInt(scoreDiagnostics['threshold_pass_count']) ?? _scorePassCount;
        _scoreTotalCount =
            _asInt(scoreDiagnostics['total_scored']) ?? _scoreTotalCount;
        _scorePassRate = _asDouble(scoreDiagnostics['threshold_pass_rate']) ??
            _scorePassRate;
      }
      final detail = _step2Summary();
      step2Detail.value = detail;
      loadingSubtext.value = detail;
      return;
    }

    if (stageName == 'stage05_topk') {
      final diagnostics = _asMap(stageData['topk_diagnostics']);
      final supportK = _asInt(diagnostics?['support_selected_k']) ?? 0;
      final skepticK = _asInt(diagnostics?['skeptic_selected_k']) ?? 0;
      final supportTrust = _asDouble(diagnostics?['support_avg_trust']);
      final skepticTrust = _asDouble(diagnostics?['skeptic_avg_trust']);
      final detail =
          '지지 $supportK건 / 반박 $skepticK건 · 평균 trust ${_formatTrust(supportTrust)} / ${_formatTrust(skepticTrust)}';
      step2Detail.value = detail;
      loadingSubtext.value = detail;
      return;
    }

    if (stageName == 'stage06_verify_support') {
      final supportPack = _asMap(stageData['verdict_support']) ??
          _asMap(stageData['support_pack']);
      if (supportPack != null) {
        final stance = _stanceLabel(supportPack['stance']);
        final confidencePct = _formatConfidencePct(supportPack['confidence']);
        final count = _citationCountFromPack(supportPack);
        final representative = _representativeCitation(supportPack);
        final detail = representative.isNotEmpty
            ? '지지 판정: $stance ($confidencePct) · 인용 $count건 · 대표 "$representative"'
            : '지지 판정: $stance ($confidencePct) · 인용 $count건';
        step3Detail.value = detail;
        loadingSubtext.value = detail;
      }
      return;
    }

    if (stageName == 'stage07_verify_skeptic') {
      final skepticPack = _asMap(stageData['verdict_skeptic']) ??
          _asMap(stageData['skeptic_pack']);
      if (skepticPack != null) {
        final stance = _stanceLabel(skepticPack['stance']);
        final confidencePct = _formatConfidencePct(skepticPack['confidence']);
        final count = _citationCountFromPack(skepticPack);
        final representative = _representativeCitation(skepticPack);
        final detail = representative.isNotEmpty
            ? '반박 판정: $stance ($confidencePct) · 인용 $count건 · 대표 "$representative"'
            : '반박 판정: $stance ($confidencePct) · 인용 $count건';
        step3Detail.value = detail;
        loadingSubtext.value = detail;
      }
      return;
    }

    if (stageName == 'stage08_aggregate') {
      final prepMeta = _asMap(stageData['judge_prep_meta']);
      if (prepMeta != null) {
        final supportCount = _asInt(prepMeta['support_citation_count']) ?? 0;
        final skepticCount = _asInt(prepMeta['skeptic_citation_count']) ?? 0;
        _supportCitationCount = supportCount;
        _skepticCitationCount = skepticCount;
        final insufficient = supportCount + skepticCount == 0;
        final detail = insufficient
            ? '지지 인용 $supportCount건 / 반박 인용 $skepticCount건 · 근거 부족'
            : '지지 인용 $supportCount건 / 반박 $skepticCount건 · 판정 준비 완료';
        step3Detail.value = detail;
        loadingSubtext.value = detail;
        return;
      }

      final supportPack = _asMap(stageData['support_pack']);
      final skepticPack = _asMap(stageData['skeptic_pack']);
      final supportCount = _citationCountFromPack(supportPack);
      final skepticCount = _citationCountFromPack(skepticPack);
      _supportCitationCount = supportCount;
      _skepticCitationCount = skepticCount;
      final insufficient = supportCount + skepticCount == 0;
      final detail = insufficient
          ? '지지 인용 $supportCount건 / 반박 인용 $skepticCount건 · 근거 부족'
          : '지지 인용 $supportCount건 / 반박 $skepticCount건 · 판정 준비 완료';
      step3Detail.value = detail;
      loadingSubtext.value = detail;
      return;
    }

    if (stageName == 'stage09_judge') {
      final finalVerdict = _asMap(stageData['final_verdict']) ?? stageData;
      final label = _stanceLabel(finalVerdict['label']);
      final confidence = _formatConfidencePct(
        finalVerdict.containsKey('confidence')
            ? finalVerdict['confidence']
            : finalVerdict['confidence_percent'],
      );
      final selectedCount = _selectedEvidenceCount(stageData, finalVerdict);
      final flags = _riskFlags(finalVerdict['risk_flags']);
      final hasNoCitations = flags.contains('NO_VERIFIED_CITATIONS');
      final shouldCapHint = flags.contains('LOW_CONFIDENCE') ||
          flags.contains('LOW_TRUST_EVIDENCE') ||
          flags.contains('JUDGE_FAIL_CLOSED') ||
          hasNoCitations;

      final detailLines = <String>[];
      if (hasNoCitations) {
        detailLines.add('근거 0건으로 판단 보류 (NO_VERIFIED_CITATIONS)');
      } else {
        detailLines.add('최종 판정: $label ($confidence)');
      }
      detailLines.add(
          '지지 $_supportCitationCount건 / 반박 $_skepticCitationCount건 중 검증 인용: $selectedCount건');
      if (flags.isNotEmpty) {
        detailLines.add('risk: ${flags.take(3).join(', ')}');
      }
      if (shouldCapHint) {
        detailLines.add('최종 판정은 근거 기반 상한으로 조정됨');
      }
      final detail = detailLines.join('\n');
      step3Detail.value = detail;
      loadingSubtext.value = detail;
    }
  }

  String _heartbeatSubtext(String? stageName, int? idleMs) {
    final stageHint = _stageHint(stageName);
    final idleSeconds = idleMs != null ? (idleMs ~/ 1000) : null;
    if (stageHint != null && idleSeconds != null) {
      return '$stageHint 단계 분석 진행 중... (${idleSeconds}s)';
    }
    if (stageHint != null) {
      return '$stageHint 단계 분석 진행 중...';
    }
    if (idleSeconds != null) {
      return '분석 진행 중... (${idleSeconds}s)';
    }
    return '분석 진행 중...';
  }

  String? _stageHint(String? stageName) {
    if (stageName == null || stageName.isEmpty || stageName == 'initializing') {
      return null;
    }
    if (stageName.startsWith('stage01') ||
        stageName.startsWith('stage02') ||
        stageName == 'adapter_queries') {
      return '주장/콘텐츠 추출';
    }
    if (stageName.startsWith('stage03') ||
        stageName.startsWith('stage04') ||
        stageName.startsWith('stage05')) {
      return '관련 근거 수집';
    }
    if (stageName.startsWith('stage06') ||
        stageName.startsWith('stage07') ||
        stageName.startsWith('stage08') ||
        stageName.startsWith('stage09')) {
      return '근거 기반 판단';
    }
    return stageName;
  }

  void _updateLoadingText(String stageName) {
    if (stageName.contains('stage01') ||
        stageName.contains('stage02') ||
        stageName.contains('normalize') ||
        stageName.contains('adapter')) {
      loadingStep.value = 0;
      loadingHeadline.value = _headlineByStep(1);
      loadingSubtext.value = _subtextByStep(1);
      return;
    }
    if (stageName.contains('stage03') ||
        stageName.contains('stage04') ||
        stageName.contains('stage05') ||
        stageName.contains('wiki') ||
        stageName.contains('web') ||
        stageName.contains('collect') ||
        stageName.contains('score') ||
        stageName.contains('topk')) {
      loadingStep.value = 1;
      loadingHeadline.value = _headlineByStep(2);
      loadingSubtext.value = _subtextByStep(2);
      return;
    }
    if (stageName.contains('stage06') ||
        stageName.contains('stage07') ||
        stageName.contains('stage08') ||
        stageName.contains('stage09') ||
        stageName.contains('verify') ||
        stageName.contains('judge') ||
        stageName.contains('aggregate')) {
      loadingStep.value = 2;
      loadingHeadline.value = _headlineByStep(3);
      loadingSubtext.value = _subtextByStep(3);
    }
  }

  String _headlineByStep(int step) {
    switch (step) {
      case 1:
        return '주장/콘텐츠 추출 중';
      case 2:
        return '관련 근거 수집 중';
      case 3:
        return '근거 기반 판단 제공 중';
      default:
        return '검증 중이에요';
    }
  }

  String _subtextByStep(int step) {
    switch (step) {
      case 1:
        return step1Detail.value;
      case 2:
        return step2Detail.value;
      case 3:
        return step3Detail.value;
      default:
        return '근거를 수집하고 있어요.';
    }
  }

  Map<String, dynamic> _extractGatewayResultPayload(Map<String, dynamic> raw) {
    final direct = Map<String, dynamic>.from(raw);

    if (direct['label'] is String) {
      return direct;
    }

    final data = _asMap(direct['data']);
    if (data != null) {
      if (data['label'] is String) {
        return data;
      }
      final nestedFinalVerdict = _asMap(data['final_verdict']);
      if (nestedFinalVerdict != null) {
        return nestedFinalVerdict;
      }
    }

    final finalVerdict = _asMap(direct['final_verdict']);
    if (finalVerdict != null) {
      return finalVerdict;
    }

    return direct;
  }

  String _buildReasonText(VerificationResult result) {
    final explanation = (result.explanation ?? '').trim();
    if (explanation.isNotEmpty) {
      return explanation;
    }

    if (result.rationale.isNotEmpty) {
      return result.rationale.take(2).join('\n');
    }

    if (result.limitations.isNotEmpty) {
      return result.limitations.take(2).join('\n');
    }

    final summary = result.summary.trim();
    if (summary.isNotEmpty) {
      return summary;
    }
    return '분석이 완료되었습니다.';
  }

  String _appendRiskHint(String reason, VerificationResult result) {
    final hints = <String>[];
    final flags = result.riskFlags.map((f) => f.toUpperCase()).toSet();
    if (flags.contains('NO_VERIFIED_CITATIONS')) {
      hints.add('검증 가능한 인용 근거가 부족해 판단을 보류했습니다.');
    }
    if (flags.contains('LOW_CONFIDENCE')) {
      hints.add('신뢰도가 낮아 추가 확인이 필요합니다.');
    }
    if (flags.contains('JUDGE_SELF_CONTRADICTION')) {
      hints.add('판정 문장 내부 모순이 감지되어 보수적으로 처리되었습니다.');
    }
    if (hints.isEmpty) {
      return reason;
    }
    return '$reason\n\n${hints.join('\n')}';
  }

  void _processResult(Map<String, dynamic> resultMap) {
    final payload = _extractGatewayResultPayload(resultMap);
    final parsed = VerificationResult.fromJson(payload);

    verdictType.value = _parseVerdict(parsed.label);
    confidence.value = parsed.confidence.clamp(0.0, 1.0);

    final headlineCandidate = (parsed.headline ?? parsed.summary).trim();
    successHeadline.value =
        (headlineCandidate.isNotEmpty && headlineCandidate.length < 80)
            ? headlineCandidate
            : _defaultHeadline(verdictType.value);

    final reason = _buildReasonText(parsed);
    successReason.value = _appendRiskHint(reason, parsed);

    evidenceCards.value =
        parsed.citations.map(EvidenceCard.fromJson).toList(growable: false);
  }

  VerdictType _parseVerdict(String label) {
    switch (label.toUpperCase()) {
      case 'TRUE':
        return VerdictType.trueClaim;
      case 'FALSE':
        return VerdictType.falseClaim;
      case 'MIXED':
        return VerdictType.mixed;
      default:
        return VerdictType.unverified;
    }
  }

  @override
  void onClose() {
    _stopStreamWatchdog();
    super.onClose();
  }
}
