import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../result_controller.dart';
import '../states/result_success_view.dart';

/// ✅ 검증 결과가 없을 때 표시되는 Empty State 화면
/// 화면설계도: Result_Empty_UI
class ResultEmptyView extends GetView<ResultController> {
  const ResultEmptyView({super.key});

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
                // Neutral Icon
                // ─────────────────────────────
                Container(
                  width: 80,
                  height: 80,
                  decoration: BoxDecoration(
                    color: isDark
                        ? theme.colorScheme.surfaceContainerHighest
                        : const Color(0xFFF2F4F7),
                    borderRadius: BorderRadius.circular(20),
                  ),
                  child: Icon(
                    PhosphorIconsRegular.magnifyingGlass,
                    size: 44,
                    color: Theme.of(
                      context,
                    ).colorScheme.onSurface.withValues(alpha: 0.5),
                  ),
                ),
                const SizedBox(height: 24),

                // ─────────────────────────────
                // Headline
                // ─────────────────────────────
                Text(
                  '결과를 찾을 수 없어요',
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
                  '검색 결과를 찾지 못했어요.\n다른 검색어로 다시 시도해 주세요.',
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
