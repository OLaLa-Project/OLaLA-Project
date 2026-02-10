import 'package:flutter/material.dart';
import 'package:get/get.dart';
import '../settings/settings_screen.dart';
import '../../shared/storage/local_storage.dart';
import '../history/history_screen.dart';
import '../bookmark/bookmark_screen.dart';
import '../verify/presentation/result_screen.dart'; // 경로는 실제 위치에 맞게 조정

/// 입력 모드 열거형
enum InputMode { url, text }

/// 스낵바 타입 (bool 플래그 대신 명시적 의도 전달)
enum SnackbarType { info, error, success, warning }

/// HomeInput 화면의 상태 관리 컨트롤러
///
/// 주요 책임:
/// - 입력 모드(URL/Text) 상태 관리
/// - 텍스트 입력 상태 관리
/// - Coach 오버레이 표시 상태 및 타겟 Rect 측정
class HomeInputController extends GetxController {
  // ═══════════════════════════════════════════════════════════════════════════
  // 상태 (Observable)
  // ═══════════════════════════════════════════════════════════════════════════

  /// 현재 입력 모드 (URL 또는 Text)
  final Rx<InputMode> mode = InputMode.url.obs;

  /// 도움말 화면 표시 여부
  final RxBool showHelp = false.obs;

  /// Coach 오버레이 표시 여부
  final RxBool showCoach = false.obs;

  /// 검증 진행 중 여부
  final RxBool isVerifying = false.obs;

  // ═══════════════════════════════════════════════════════════════════════════
  // 텍스트 컨트롤러
  // ═══════════════════════════════════════════════════════════════════════════

  final TextEditingController textController = TextEditingController();

  // ═══════════════════════════════════════════════════════════════════════════
  // Coach 타겟 GlobalKey (Rect 측정용)
  // ═══════════════════════════════════════════════════════════════════════════

  final GlobalKey settingsKey = GlobalKey(debugLabel: 'coach_settings');
  final GlobalKey selectorKey = GlobalKey(debugLabel: 'coach_selector');
  final GlobalKey inputAreaKey = GlobalKey(debugLabel: 'coach_inputArea');
  final GlobalKey inputClearButtonKey = GlobalKey(
    debugLabel: 'coach_input_clear',
  );
  final GlobalKey verifyButtonKey = GlobalKey(debugLabel: 'coach_verify');

  // ═══════════════════════════════════════════════════════════════════════════
  // Coach 타겟 Rect (측정된 위치/크기)
  // ═══════════════════════════════════════════════════════════════════════════

  final Rxn<Rect> settingsRect = Rxn<Rect>();
  final Rxn<Rect> selectorRect = Rxn<Rect>();
  final Rxn<Rect> inputRect = Rxn<Rect>();
  final Rxn<Rect> inputClearRect = Rxn<Rect>();
  final Rxn<Rect> verifyRect = Rxn<Rect>();

  // ═══════════════════════════════════════════════════════════════════════════
  // 상수
  // ═══════════════════════════════════════════════════════════════════════════

  static const String _urlHint =
      '검증할 URL을 붙여넣어 주세요.\n예) https://example.com/news/123';
  static const String _textHint =
      '검증할 문장을 입력해 주세요.\n예) "OOO는 2024년에 노벨상을 받았다."';
  static const Duration _coachShowDelay = Duration(milliseconds: 300);

  // Snackbar 정책(파일 내부 표준화)
  static const EdgeInsets _snackMargin = EdgeInsets.all(16);
  static const double _snackRadius = 12;
  static const Duration _snackDuration = Duration(seconds: 2);

  // ═══════════════════════════════════════════════════════════════════════════
  // Getters
  // ═══════════════════════════════════════════════════════════════════════════

  /// 현재 모드에 맞는 placeholder 텍스트
  String get placeholder => mode.value == InputMode.url ? _urlHint : _textHint;

  /// 입력값이 비어있는지 여부
  bool get isInputEmpty => textController.text.trim().isEmpty;

  // ═══════════════════════════════════════════════════════════════════════════
  // Lifecycle
  // ═══════════════════════════════════════════════════════════════════════════

  @override
  void onInit() {
    super.onInit();
    _initializeCoachIfNeeded();
  }

  @override
  void onReady() {
    super.onReady();
    _setupRectMeasurement();
  }

  @override
  void onClose() {
    textController.dispose();
    super.onClose();
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // 초기화 메서드 (Private)
  // ═══════════════════════════════════════════════════════════════════════════

  /// 첫 실행 시 Coach 오버레이 자동 표시
  Future<void> _initializeCoachIfNeeded() async {
    final isCoachCompleted = await LocalStorage.isCoachCompleted();
    if (!isCoachCompleted) {
      // 화면 전환 애니메이션 완료 대기
      await Future.delayed(_coachShowDelay);
      showCoach.value = true;
      _scheduleMeasurement();
    }
  }

  /// Rect 측정 리스너 설정
  void _setupRectMeasurement() {
    // 첫 프레임 이후 측정
    _scheduleMeasurement();

    // 모드 변경 또는 Coach 상태 변경 시 재측정
    everAll([mode, showCoach], (_) => _scheduleMeasurement());
  }

  /// 다음 프레임에서 Rect 측정 예약
  void _scheduleMeasurement() {
    WidgetsBinding.instance.addPostFrameCallback((_) => captureCoachRects());
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // 입력 모드 관련 (Public)
  // ═══════════════════════════════════════════════════════════════════════════

  /// 입력 모드 변경
  void setMode(InputMode newMode) {
    if (mode.value == newMode) return;
    mode.value = newMode;
  }

  /// 입력 필드 초기화
  void clearInput() => textController.clear();

  // ═══════════════════════════════════════════════════════════════════════════
  // 도움말 관련 (Public)
  // ═══════════════════════════════════════════════════════════════════════════

  void openHelp() => showHelp.value = true;
  void closeHelp() => showHelp.value = false;

  // ═══════════════════════════════════════════════════════════════════════════
  // 네비게이션 (Public)
  // ═══════════════════════════════════════════════════════════════════════════

  void goSettings() {
    if (showCoach.value) return;
    Get.to(() => const SettingsScreen());
  }

  void goHistory() => Get.to(() => const HistoryScreen());
  void goBookmark() => Get.to(() => const BookmarkScreen());

  /// 홈 화면 새로고침 (입력 초기화 + URL 모드)
  void refreshHome() {
    mode.value = InputMode.url;
    clearInput();
    update();
    _scheduleMeasurement();
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // Coach 관련 (Public)
  // ═══════════════════════════════════════════════════════════════════════════

  /// Coach 오버레이 닫기 및 완료 상태 저장
  Future<void> closeCoach() async {
    await LocalStorage.setCoachCompleted();
    await LocalStorage.setFirstLaunchCompleted();
    showCoach.value = false;
  }

  /// Coach 타겟 요소들의 Rect 측정
  void captureCoachRects() {
    selectorRect.value = _measureRect(selectorKey);
    inputRect.value = _measureRect(inputAreaKey);
    inputClearRect.value = _measureRect(inputClearButtonKey);
    verifyRect.value = _measureRect(verifyButtonKey);
  }

  /// GlobalKey로부터 Rect 측정
  // ───────────────────────────────────────────────────────────────────────────

  Rect? _measureRect(GlobalKey key) {
    final context = key.currentContext;
    if (context == null) return null;

    final renderObject = context.findRenderObject();
    if (renderObject is! RenderBox || !renderObject.hasSize) return null;

    final offset = renderObject.localToGlobal(Offset.zero);
    return offset & renderObject.size;
  }

  /// Help 오버레이를 띄우기 직전에 호출: HomeInput 영역 Rect를 최신으로 측정
  Future<void> captureHelpRects() async {
    await Future<void>.delayed(_coachShowDelay);
    settingsRect.value = _measureRect(settingsKey);
    selectorRect.value = _measureRect(selectorKey);
    inputRect.value = _measureRect(inputAreaKey);
    inputClearRect.value = _measureRect(inputClearButtonKey);
    verifyRect.value = _measureRect(verifyButtonKey);
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // 검증 관련 (Public)
  // ═══════════════════════════════════════════════════════════════════════════

  /// 검증 시작
  Future<void> startVerify() async {
    // 입력값 검증
    if (isInputEmpty) {
      _showSnackbar(
        title: '입력 필요',
        message: '검증할 내용을 입력해 주세요.',
        type: SnackbarType.warning,
      );
      return;
    }

    // 중복 실행 방지
    if (isVerifying.value) return;

    try {
      isVerifying.value = true;
      await _performVerification();
    } catch (_) {
      _showSnackbar(
        title: '오류',
        message: '검증 중 오류가 발생했습니다.',
        type: SnackbarType.error,
      );
    } finally {
      isVerifying.value = false;
    }
  }

  /// 실제 검증 수행 (향후 FastAPI 연동)
  Future<void> _performVerification() async {
    final input = textController.text.trim();
    final inputMode = mode.value;

    // ✅ ResultScreen에서 사용할 입력값 전달
    final args = {
      'mode': inputMode.name, // 'url' or 'text'
      'input': input,
    };

    // ✅ ResultScreen으로 이동하면 ResultLoading UI가 즉시 뜹니다.
    Get.to(() => const ResultScreen(), arguments: args);

    // ❌ 기존 "연동 전" 스낵바는 제거(또는 주석)
    // _showSnackbar(
    //   title: '검증 시작',
    //   message: 'AI 검증 연동 전입니다. (추후 FastAPI 연결)',
    //   type: SnackbarType.info,
    // );
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // UI Helpers (Private) - 파일 내부 표준화
  // ═══════════════════════════════════════════════════════════════════════════

  /// 스낵바 표시 헬퍼
  ///
  /// 표준 정책:
  /// - 테마(ColorScheme) 기반 컬러
  /// - 겹침 방지(기존 스낵바 닫기)
  /// - 매직넘버 제거(상수화)
  void _showSnackbar({
    required String title,
    required String message,
    SnackbarType type = SnackbarType.info,
  }) {
    final t = title.trim();
    final m = message.trim();

    assert(t.isNotEmpty, 'Snackbar title must not be empty');
    assert(m.isNotEmpty, 'Snackbar message must not be empty');

    // 겹침 방지
    if (Get.isSnackbarOpen) {
      Get.closeCurrentSnackbar();
    }

    final cs = Get.theme.colorScheme;
    final (bg, fg) = _snackColors(cs, type);

    Get.snackbar(
      t,
      m,
      snackPosition: SnackPosition.BOTTOM,
      backgroundColor: bg,
      colorText: fg,
      margin: _snackMargin,
      borderRadius: _snackRadius,
      duration: _snackDuration,
    );
  }

  /// Snackbar 색 정책 (테마 기반)
  (Color background, Color foreground) _snackColors(
    ColorScheme cs,
    SnackbarType type,
  ) {
    switch (type) {
      case SnackbarType.error:
        return (cs.errorContainer, cs.onErrorContainer);
      case SnackbarType.success:
        return (cs.tertiaryContainer, cs.onTertiaryContainer);
      case SnackbarType.warning:
        return (cs.secondaryContainer, cs.onSecondaryContainer);
      case SnackbarType.info:
        return (cs.primaryContainer, cs.onPrimaryContainer);
    }
  }
}
