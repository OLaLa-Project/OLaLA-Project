import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import 'bookmark_controller.dart';
import 'widgets/bookmark_list_item.dart';

// Shell 탭 전환
import '../shell/shell_controller.dart';

// 설정 이동
import '../settings/settings_screen.dart';

class BookmarkScreen extends StatelessWidget {
  const BookmarkScreen({super.key});

  @override
  Widget build(BuildContext context) {
    Get.lazyPut<BookmarkController>(() => BookmarkController());
    final c = Get.find<BookmarkController>();

    final shell =
        Get.isRegistered<ShellController>() ? Get.find<ShellController>() : null;

    return Scaffold(
      backgroundColor: Color(0xFFF7F7F7),
      appBar: AppBar(
      backgroundColor: Colors.white,
      foregroundColor: Colors.black,
      elevation: 0,
      surfaceTintColor: Colors.white, // M3 색 섞임 방지
      toolbarHeight: 56,
      shape: Border(
        bottom: BorderSide(
          color: Colors.black.withOpacity(0.06),
          width: 1,
          ),
        ),
        leading: IconButton(
          tooltip: '뒤로가기',
          icon: const Icon(
            PhosphorIconsRegular.caretLeft,
            size: 32,
          ),
          onPressed: () {
            if (Navigator.of(context).canPop()) {
              Navigator.of(context).pop();
              return;
            }
            shell?.setTab(1); // 홈 탭
          },
        ),
        title: const Text(
          'BookMark',
          style: TextStyle(
            fontSize: 30,
            fontWeight: FontWeight.w400,
          ),
        ),
        centerTitle: true,
        actions: [
          SettingsIconButton(
            onPressed: () => Get.to(() => const SettingsScreen()),
          ),
        ],
      ),
      body: SafeArea(
        child: Obx(() {
          if (c.items.isEmpty) {
            return const _EmptyBookmark();
          }

          return ListView.separated(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
            itemCount: c.items.length,
            separatorBuilder: (_, __) => const SizedBox(height: 12),
            itemBuilder: (context, index) {
              final item = c.items[index];
              return BookmarkListItem(
                item: item,
                onTap: () {
                  // TODO: Result_UI 연결
                },
                onToggleOff: () => c.toggleOff(item.id),
              );
            },
          );
        }),
      ),
    );
  }
}

/// ===============================
///  Settings Icon Button
/// ===============================

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
      behavior: HitTestBehavior.opaque,
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) {
        setState(() => _pressed = false);
        widget.onPressed();
      },
      onTapCancel: () => setState(() => _pressed = false),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8),
        child: Icon(
          _pressed ? PhosphorIconsFill.gear : PhosphorIconsRegular.gear,
          size: 32,
          color: _pressed ? Colors.black : null,
        ),
      ),
    );
  }
}

class _EmptyBookmark extends StatelessWidget {
  const _EmptyBookmark();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      color: Color(0xFFF7F7F7),
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                PhosphorIconsRegular.bookmarkSimple,
                size: 44,
                color: theme.colorScheme.onSurface.withOpacity(0.5),
              ),
              const SizedBox(height: 10),
              const Text(
                '북마크가 비어있어요',
                style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16),
              ),
              const SizedBox(height: 6),
              Text(
                '결과 화면에서 북마크를 누르면 여기에 모아볼 수 있어요.',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: theme.colorScheme.onSurface.withOpacity(0.7),
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
