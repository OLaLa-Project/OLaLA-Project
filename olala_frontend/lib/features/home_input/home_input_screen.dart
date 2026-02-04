import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import 'home_input_controller.dart';
import 'widgets/input_type_selector.dart';
import 'widgets/input_field.dart';
import 'widgets/verify_start_button.dart';
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

    return Scaffold(
      backgroundColor: Colors.white,
      body: Stack(
        children: [
          _MainContent(controller: controller),

          // 도움말 FAB (Coach 떠 있으면 숨김)
          Obx(() => controller.showCoach.value
              ? const SizedBox.shrink()
              : Positioned(
                  right: 16,
                  bottom: 16,
                  child: _HelpFab(
                    onPressed: () => _navigateToHelp(context),
                  ),
                )),

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

  void _navigateToHelp(BuildContext context) {
    Navigator.of(context).push(
      MaterialPageRoute(builder: (_) => const HelpScreen()),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// 메인 콘텐츠
// ═══════════════════════════════════════════════════════════════════════════════

class _MainContent extends StatelessWidget {
  final HomeInputController controller;
  const _MainContent({required this.controller});

  static const Color bodyBg = Color(0xFFF7F7F7);

  @override
  Widget build(BuildContext context) {
    return SafeArea(
      child: Container(
        color: bodyBg,
        child: Column(
          children: [
            Obx(() => _CustomAppBar(
                  onSettingsTap: controller.goSettings,
                  hideSettings: controller.showCoach.value,
                )),
            Expanded(
              child: _InputSection(controller: controller),
            ),
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

  const _CustomAppBar({
    required this.onSettingsTap,
    required this.hideSettings,
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 56,
      padding: const EdgeInsets.symmetric(horizontal: 16),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border(
          bottom: BorderSide(
            color: Colors.black.withOpacity(0.06),
            width: 1,
          ),
        ),
      ),
      child: Row(
        children: [
          const SizedBox(width: kMinInteractiveDimension),

          Expanded(
            child: Center(child: _buildTitle()),
          ),

          SizedBox(
            width: kMinInteractiveDimension,
            child: hideSettings
                ? const SizedBox.shrink()
                : SettingsIconButton(onPressed: onSettingsTap),
          ),
        ],
      ),
    );
  }

  Widget _buildTitle() {
    if (hideSettings) {
      // ✅ 오버레이 떠 있을 때: 글자만 숨김 (레이아웃 유지)
      return const SizedBox(height: 30);
    }

    // ✅ 평소: 기존 그대로
    return const Text(
      'OLaLA',
      style: TextStyle(
        fontSize: 30,
        fontWeight: FontWeight.w400,
        color: Colors.black,
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
    return GestureDetector(
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) {
        setState(() => _pressed = false);
        widget.onPressed();
      },
      onTapCancel: () => setState(() => _pressed = false),
      child: Icon(
        _pressed
            ? PhosphorIconsFill.gear
            : PhosphorIconsRegular.gear,
        size: 32.0,

        color: _pressed ? Colors.black : null,

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
          Obx(() => InputTypeSelector(
                containerKey: controller.selectorKey,
                selected: controller.mode.value,
                onSelectUrl: () => controller.setMode(InputMode.url),
                onSelectText: () => controller.setMode(InputMode.text),
              )),
          const SizedBox(height: 12),
          SizedBox(
            height: 300,
            child: Obx(() => InputField(
                  containerKey: controller.inputAreaKey,
                  controller: controller.textController,
                  placeholder: controller.placeholder,
                  onClear: controller.clearInput,
                )),
          ),
          const SizedBox(height: 12),
          Obx(() => VerifyStartButton(
                containerKey: controller.verifyButtonKey,
                onPressed: controller.startVerify,
                isLoading: controller.isVerifying.value,
              )),
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

  static const _primaryColor = Color.fromARGB(255, 255, 255, 255);

  @override
  Widget build(BuildContext context) {
    return Container(
      decoration: BoxDecoration(
        shape: BoxShape.circle,
        color: _primaryColor, // 단색 배경
        boxShadow: const [
          BoxShadow(
            color: Colors.black26, // ✅ 검은 그림자
            blurRadius: 3,        // 퍼짐 정도
            offset: Offset(0, 1), // 아래쪽으로 그림자
          ),
        ],
      ),
      child: Material(
        color: Colors.transparent,
        child: InkWell(
          onTap: onPressed,
          borderRadius: BorderRadius.circular(28),
          child: const SizedBox(
            width: 44,
            height: 44,
            child: Center(
              child: Text(
                '도움말',
                style: TextStyle(
                  color: Color(0xFF616161), // 기존 아이콘 색 유지
                  fontSize: 12,             // 아이콘 size 20보다 작게
                  fontWeight: FontWeight.w400, // 얇게
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
