import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../home_input/home_input_screen.dart';
import '../history/history_screen.dart';
import '../bookmark/bookmark_screen.dart';
import 'shell_controller.dart';

class ShellScreen extends StatefulWidget {
  const ShellScreen({super.key});

  @override
  State<ShellScreen> createState() => _ShellScreenState();
}

class _ShellScreenState extends State<ShellScreen> {
  late final ShellController c;

  @override
  void initState() {
    super.initState();
    c = Get.put(ShellController(), permanent: true);
    WidgetsBinding.instance.addPostFrameCallback((_) => _captureNavRects());
  }

  Rect? _measureRect(GlobalKey key) {
    final ctx = key.currentContext;
    if (ctx == null) return null;
    final ro = ctx.findRenderObject();
    if (ro is! RenderBox || !ro.hasSize) return null;
    final o = ro.localToGlobal(Offset.zero);
    return o & ro.size;
  }

  void _captureNavRects() {
    final h = _measureRect(c.navHistoryKey);
    final v = _measureRect(c.navVerifyKey);
    final b = _measureRect(c.navBookmarkKey);
    c.updateNavRects(history: h, verify: v, bookmark: b);
  }

  @override
  Widget build(BuildContext context) {
    final pages = const [HistoryScreen(), HomeInputScreen(), BookmarkScreen()];
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return Obx(() {
      // 탭 변경/리빌드 후에도 rect가 바뀔 수 있어 다시 측정
      WidgetsBinding.instance.addPostFrameCallback((_) => _captureNavRects());

      return Scaffold(
        body: IndexedStack(index: c.tabIndex.value, children: pages),
        bottomNavigationBar: Container(
          decoration: BoxDecoration(
            color: isDark ? theme.colorScheme.surface : Colors.white,
            border: Border(
              top: BorderSide(
                color: isDark
                    ? theme.colorScheme.outlineVariant.withValues(alpha: 0.6)
                    : Colors.transparent,
                width: 1,
              ),
            ),
            boxShadow: isDark
                ? const []
                : [
                    BoxShadow(
                      color: Colors.black.withOpacity(0.06),
                      blurRadius: 0,
                      offset: const Offset(0, -1),
                    ),
                  ],
          ),
          child: NavigationBarTheme(
            data: NavigationBarThemeData(
              indicatorColor: Colors.transparent,
              overlayColor: WidgetStateProperty.all(Colors.transparent),
              backgroundColor: isDark
                  ? theme.colorScheme.surface
                  : Colors.white,
              iconTheme: WidgetStateProperty.resolveWith<IconThemeData>((
                states,
              ) {
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
              selectedIndex: c.tabIndex.value,
              onDestinationSelected: c.setTab,
              destinations: [
                NavigationDestination(
                  icon: KeyedSubtree(
                    key: c.navHistoryKey,
                    child: const Icon(
                      PhosphorIconsRegular.clockCounterClockwise,
                    ),
                  ),
                  label: '히스토리',
                ),
                NavigationDestination(
                  icon: KeyedSubtree(
                    key: c.navVerifyKey,
                    child: const Icon(PhosphorIconsRegular.magnifyingGlass),
                  ),
                  label: '검색',
                ),
                NavigationDestination(
                  icon: KeyedSubtree(
                    key: c.navBookmarkKey,
                    child: const Icon(PhosphorIconsRegular.bookmarkSimple),
                  ),
                  label: '북마크',
                ),
              ],
            ),
          ),
        ),
      );
    });
  }
}
