import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../home_input/home_input_screen.dart';
import '../history/history_screen.dart';
import '../bookmark/bookmark_screen.dart';
import 'shell_controller.dart';

class ShellScreen extends StatelessWidget {
  const ShellScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final c = Get.put(ShellController(), permanent: true);

    final pages = const [HistoryScreen(), HomeInputScreen(), BookmarkScreen()];

    return Obx(() {
      return Scaffold(
        body: IndexedStack(index: c.tabIndex.value, children: pages),

        bottomNavigationBar: Container(
          decoration: BoxDecoration(
            color: Colors.white,
            boxShadow: [
              BoxShadow(
                color: Colors.black.withOpacity(0.06), // 👈 지금 border랑 동일 농도
                blurRadius: 0,                         // 👈 퍼짐 없음 = 선처럼 보이게
                offset: const Offset(0, -1),           // 👈 위쪽에만
              ),
            ],
          ),
          child: NavigationBarTheme(
            data: NavigationBarThemeData(
              indicatorColor: Colors.transparent,
              overlayColor: WidgetStateProperty.all(Colors.transparent),
              backgroundColor: Colors.white,
              iconTheme: WidgetStateProperty.resolveWith<IconThemeData>((states) {
                final selected = states.contains(WidgetState.selected);
                return IconThemeData(
                  size: 32,
                  color: selected ? Colors.black : const Color(0xff7a7a7a),
                );
              }),
              labelTextStyle: WidgetStateProperty.resolveWith<TextStyle>((states) {
                final selected = states.contains(WidgetState.selected);
                return TextStyle(
                  color: selected ? Colors.black : const Color(0xff7a7a7a),
                  fontSize: 12,
                );
              }),
            ),
            child: NavigationBar(
              selectedIndex: c.tabIndex.value,
              onDestinationSelected: c.setTab,
              destinations: const [
                NavigationDestination(
                  icon: Icon(PhosphorIconsRegular.clockCounterClockwise),
                  label: '히스토리',
                ),
                NavigationDestination(
                  icon: Icon(PhosphorIconsRegular.magnifyingGlass),
                  label: '검색',
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
    });
  }
}
