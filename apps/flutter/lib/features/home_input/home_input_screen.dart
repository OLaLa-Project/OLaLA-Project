import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import 'home_input_controller.dart';
import '../shell/shell_controller.dart';
import 'help/widgets/tutorial_content.dart';
import 'widgets/input_type_selector.dart';
import 'widgets/input_field.dart';
import 'widgets/verify_start_button.dart';
import 'widgets/issue_banner.dart';
import 'help/help_screen.dart';
import '../coach/coach_controller.dart';
import '../coach/widgets/coach_overlay.dart';

/// 홈 입력 화면
class HomeInputScreen extends StatelessWidget {
  const HomeInputScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final controller = Get.put(HomeInputController());
    final coachController = Get.put(CoachController(), tag: 'homeCoach');
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final bodyBg = isDark
        ? theme.colorScheme.surfaceVariant
        : const Color(0xFFF7F7F7);
    final scaffoldBg = isDark ? bodyBg : Colors.white;

    return Scaffold(
      backgroundColor: scaffoldBg,
      body: Stack(
        children: [
          _MainContent(controller: controller),

          // 도움말 FAB (Coach 떠 있으면 숨김)
          Obx(
            () => controller.showCoach.value
                ? const SizedBox.shrink()
                : Positioned(
                    right: 16,
                    bottom: 16,
                    child: _HelpFab(onPressed: () => _navigateToHelp(context)),
                  ),
          ),

          // Coach 오버레이 (Positioned는 Stack 직속)
          Positioned.fill(
            child: _CoachOverlayLayer(
              controller: controller,
              coachController: coachController,
            ),
          ),
        ],
      ),
    );
  }

  Future<void> _navigateToHelp(BuildContext context) async {
    final controller = Get.find<HomeInputController>();
    final shell = Get.isRegistered<ShellController>()
        ? Get.find<ShellController>()
        : null;

    // 1) HomeInput 영역 Rect 측정
    await controller.captureHelpRects();

    // 2) Shell(bottom nav) Rect 취합
    final rects = <GuideTarget, Rect?>{
      GuideTarget.settings: controller.settingsRect.value,
      GuideTarget.inputTypeSelector: controller.selectorRect.value,
      GuideTarget.inputField: controller.inputRect.value,
      GuideTarget.inputClearButton: controller.inputClearRect.value,
      GuideTarget.verifyStartButton: controller.verifyRect.value,
      GuideTarget.navHistory: shell?.navHistoryRect.value,
      GuideTarget.navVerify: shell?.navVerifyRect.value,
      GuideTarget.navBookmark: shell?.navBookmarkRect.value,
    };

    // 3) 오버레이로 표시(투명 route)
    Navigator.of(context).push(
      PageRouteBuilder(
        opaque: false,
        barrierColor: Colors.transparent,
        pageBuilder: (_, __, ___) => HelpScreen(rects: rects),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// 메인 콘텐츠
// ═══════════════════════════════════════════════════════════════════════════════

class _MainContent extends StatelessWidget {
  final HomeInputController controller;
  const _MainContent({required this.controller});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return SafeArea(
      child: Container(
        color: isDark
            ? theme.colorScheme.surfaceVariant
            : const Color(0xFFF7F7F7),
        child: Column(
          children: [
            Obx(
              () => _CustomAppBar(
                onSettingsTap: controller.goSettings,
                hideSettings: controller.showCoach.value,
                settingsKey: controller.settingsKey,
              ),
            ),
            Expanded(child: _InputSection(controller: controller)),
          ],
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// 커스텀 앱바
// ═══════════════════════════════════════════════════════════════════════════════

class _CustomAppBar extends StatelessWidget {
  final VoidCallback onSettingsTap;
  final bool hideSettings;
  final Key? settingsKey;

  const _CustomAppBar({
    required this.onSettingsTap,
    required this.hideSettings,
    this.settingsKey,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Container(
      height: 56,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: isDark ? theme.colorScheme.surface : Colors.white,
        border: Border(
          bottom: BorderSide(
            color: isDark
                ? theme.colorScheme.outlineVariant.withOpacity(0.6)
                : Colors.black.withOpacity(0.06),
            width: 1,
          ),
        ),
      ),
      child: Row(
        children: [
          const SizedBox(width: kMinInteractiveDimension),

          Expanded(child: Center(child: _buildTitle(context))),

          SizedBox(
            width: kMinInteractiveDimension,
            child: hideSettings
                ? const SizedBox.shrink()
                : SettingsIconButton(
                    key: settingsKey,
                    onPressed: onSettingsTap,
                  ),
          ),
        ],
      ),
    );
  }

  Widget _buildTitle(BuildContext context) {
    if (hideSettings) {
      // ✅ 오버레이 떠 있을 때: 글자만 숨김 (레이아웃 유지)
      return const SizedBox(height: 30);
    }

    // ✅ 평소: 기존 그대로
    return Text(
      'OLaLA',
      style: TextStyle(
        fontSize: 30,
        fontWeight: FontWeight.w400,
        color: Theme.of(context).brightness == Brightness.dark
            ? Theme.of(context).colorScheme.onSurface
            : Colors.black,
        letterSpacing: -0.5,
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// 설정 아이콘 버튼 (눌리는 동안 아이콘/색 변경)
// ═══════════════════════════════════════════════════════════════════════════════

class SettingsIconButton extends StatefulWidget {
  final VoidCallback onPressed;
  const SettingsIconButton({super.key, required this.onPressed});

  @override
  State<SettingsIconButton> createState() => _SettingsIconButtonState();
}

class _SettingsIconButtonState extends State<SettingsIconButton> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) {
        setState(() => _pressed = false);
        widget.onPressed();
      },
      onTapCancel: () => setState(() => _pressed = false),
      child: Icon(
        _pressed ? PhosphorIconsFill.gear : PhosphorIconsRegular.gear,
        size: 32.0,
        color: isDark
            ? (_pressed
                  ? theme.colorScheme.onSurface
                  : theme.colorScheme.onSurface.withOpacity(0.85))
            : (_pressed ? Colors.black : null),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// 입력 섹션
// ═══════════════════════════════════════════════════════════════════════════════

class _InputSection extends StatelessWidget {
  final HomeInputController controller;
  const _InputSection({required this.controller});

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
      child: Column(
        children: [
          // 오늘의 이슈 배너
          const IssueBanner(),
          const SizedBox(height: 12),
          Obx(
            () => InputTypeSelector(
              containerKey: controller.selectorKey,
              selected: controller.mode.value,
              onSelectUrl: () => controller.setMode(InputMode.url),
              onSelectText: () => controller.setMode(InputMode.text),
            ),
          ),
          const SizedBox(height: 12),
          SizedBox(
            height: 300,
            child: Obx(
              () => InputField(
                containerKey: controller.inputAreaKey,
                clearButtonKey: controller.inputClearButtonKey,
                controller: controller.textController,
                placeholder: controller.placeholder,
                onClear: controller.clearInput,
              ),
            ),
          ),
          const SizedBox(height: 12),
          Obx(
            () => VerifyStartButton(
              containerKey: controller.verifyButtonKey,
              onPressed: controller.startVerify,
              isLoading: controller.isVerifying.value,
            ),
          ),
        ],
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// 도움말 FAB
// ═══════════════════════════════════════════════════════════════════════════════

class _HelpFab extends StatelessWidget {
  final VoidCallback onPressed;
  const _HelpFab({required this.onPressed});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final fabBg = isDark ? theme.colorScheme.surface : Colors.white;
    final fabBorder = isDark
        ? theme.colorScheme.outlineVariant.withValues(alpha: 0.8)
        : Colors.black.withValues(alpha: 0.06);
    final fabText = isDark
        ? theme.colorScheme.onSurface
        : const Color(0xFF616161);

    return Container(
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: fabBg,
        border: Border.all(color: fabBorder, width: 1),
        boxShadow: [
          BoxShadow(
            color: isDark
                ? Colors.black.withValues(alpha: 0.7)
                : Colors.black.withValues(alpha: 0.18),
            blurRadius: isDark ? 6 : 3,
            offset: const Offset(0, 1),
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onPressed,
          borderRadius: BorderRadius.circular(28),
          child: SizedBox(
            width: 44,
            height: 44,
            child: Center(
              child: Text(
                '도움말',
                style: TextStyle(
                  color: fabText,
                  fontSize: 12,
                  fontWeight: isDark ? FontWeight.w600 : FontWeight.w400,
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// Coach 오버레이 레이어
// ═══════════════════════════════════════════════════════════════════════════════

class _CoachOverlayLayer extends StatelessWidget {
  final HomeInputController controller;
  final CoachController coachController;

  const _CoachOverlayLayer({
    required this.controller,
    required this.coachController,
  });

  @override
  Widget build(BuildContext context) {
    return Obx(() {
      if (!controller.showCoach.value) {
        return const SizedBox.shrink();
      }

      return CoachOverlay(
        coachStep: coachController.currentStep.value,
        onClose: controller.closeCoach,
        onNext: coachController.nextStep,
        onPrev: coachController.previousStep,
        onFinish: controller.closeCoach,
        selectorRect: controller.selectorRect.value,
        inputRect: controller.inputRect.value,
        verifyRect: controller.verifyRect.value,
      );
    });
  }
}
