import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../result_controller.dart';
import '../states/result_success_view.dart';

/// ✅ 검증 중 오류가 발생했을 때 표시되는 Error State 화면
/// 화면설계도: Result_Error_UI
class ResultErrorView extends GetView<ResultController> {
  const ResultErrorView({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final bg = isDark
        ? theme.colorScheme.surfaceVariant
        : const Color(0xFFF7F7F7);

    return Scaffold(
      backgroundColor: bg,
      appBar: AppBar(
        backgroundColor: isDark ? theme.colorScheme.surface : Colors.white,
        foregroundColor: isDark ? theme.colorScheme.onSurface : Colors.black,
        elevation: 0,
        surfaceTintColor: isDark ? theme.colorScheme.surface : Colors.white,
        toolbarHeight: 56,
        shape: Border(
          bottom: BorderSide(
            color: isDark
                ? theme.colorScheme.outlineVariant.withValues(alpha: 0.7)
                : Colors.black.withValues(alpha: 0.06),
            width: 1,
          ),
        ),
        leading: IconButton(
          tooltip: '뒤로가기',
          icon: const Icon(PhosphorIconsRegular.caretLeft, size: 32),
          onPressed: () => Get.back(),
        ),
        title: const Text(
          'Result',
          style: TextStyle(fontSize: 30, fontWeight: FontWeight.w400),
        ),
        centerTitle: true,
        actions: [SettingsIconButton(onPressed: controller.openSettings)],
      ),
      body: SafeArea(
        child: Center(
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 32),
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                // ─────────────────────────────
                // Error Icon
                // ─────────────────────────────
                Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    color: isDark
                        ? const Color(0xFFEF4444).withValues(alpha: 0.22)
                        : const Color(0xFFFEF2F2),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: const Icon(
                    PhosphorIconsRegular.warningCircle,
                    size: 44,
                    color: Color(0xFFEF4444),
                  ),
                ),
                const SizedBox(height: 24),

                // ─────────────────────────────
                // Headline
                // ─────────────────────────────
                Text(
                  '문제가 발생했어요',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 20,
                    fontWeight: FontWeight.w900,
                    color: isDark
                        ? theme.colorScheme.onSurface
                        : const Color(0xFF111827),
                    height: 1.3,
                  ),
                ),
                const SizedBox(height: 12),

                // ─────────────────────────────
                // Subtext
                // ─────────────────────────────
                Text(
                  '일시적인 오류가 발생했어요.\n잠시 후 다시 시도해 주세요.',
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                    color: isDark
                        ? theme.colorScheme.onSurfaceVariant
                        : const Color(0xFF6B7280),
                    height: 1.48,
                  ),
                ),
                const SizedBox(height: 32),

                // ─────────────────────────────
                // CTA Button (다시 시도하기) - Outlined
                // ─────────────────────────────
                SizedBox(
                  width: double.infinity,
                  child: OutlinedButton(
                    onPressed: () {
                      // 재시도 로직 (예: 다시 로딩 상태로 변경)
                      controller.resultState.value = ResultState.loading;
                      // TODO: 실제 검증 API 재호출 로직 추가
                    },
                    style: OutlinedButton.styleFrom(
                      foregroundColor: isDark
                          ? theme.colorScheme.onSurfaceVariant
                          : const Color(0xFF374151),
                      padding: const EdgeInsets.symmetric(vertical: 16),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                      side: BorderSide(
                        color: isDark
                            ? theme.colorScheme.outlineVariant
                            : const Color(0xFFE5E7EB),
                        width: 1.5,
                      ),
                    ),
                    child: const Text(
                      '다시 시도하기',
                      style: TextStyle(
                        fontSize: 16,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: isDark ? theme.colorScheme.surface : Colors.white,
          border: Border(
            top: BorderSide(
              color: isDark
                  ? theme.colorScheme.outlineVariant.withValues(alpha: 0.7)
                  : Colors.transparent,
              width: 1,
            ),
          ),
          boxShadow: isDark
              ? const []
              : [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.06),
                    blurRadius: 0,
                    offset: const Offset(0, -1),
                  ),
                ],
        ),
        child: NavigationBarTheme(
          data: NavigationBarThemeData(
            indicatorColor: Colors.transparent,
            overlayColor: WidgetStateProperty.all(Colors.transparent),
            backgroundColor: isDark ? theme.colorScheme.surface : Colors.white,
            iconTheme: WidgetStateProperty.resolveWith<IconThemeData>((states) {
              final selected = states.contains(WidgetState.selected);
              return IconThemeData(
                size: 32,
                color: selected
                    ? (isDark ? theme.colorScheme.onSurface : Colors.black)
                    : (isDark
                          ? theme.colorScheme.onSurfaceVariant
                          : const Color(0xff7a7a7a)),
              );
            }),
            labelTextStyle: WidgetStateProperty.resolveWith<TextStyle>((
              states,
            ) {
              final selected = states.contains(WidgetState.selected);
              return TextStyle(
                color: selected
                    ? (isDark ? theme.colorScheme.onSurface : Colors.black)
                    : (isDark
                          ? theme.colorScheme.onSurfaceVariant
                          : const Color(0xff7a7a7a)),
                fontSize: 12,
              );
            }),
          ),
          child: NavigationBar(
            selectedIndex: 1, // 검증(중앙) 탭 선택
            onDestinationSelected: (index) {
              if (index == 0) controller.goHistory();
              if (index == 1) controller.goHome();
              if (index == 2) controller.goBookmark();
            },
            destinations: const [
              NavigationDestination(
                icon: Icon(PhosphorIconsRegular.clockCounterClockwise),
                label: '히스토리',
              ),
              NavigationDestination(
                icon: Icon(PhosphorIconsRegular.magnifyingGlass),
                label: '검증',
              ),
              NavigationDestination(
                icon: Icon(PhosphorIconsRegular.bookmarkSimple),
                label: '북마크',
              ),
            ],
          ),
        ),
      ),
    );
  }
}
