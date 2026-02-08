import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import 'history_controller.dart';
import 'widgets/history_list_item.dart';

import '../shell/shell_controller.dart';
import '../settings/settings_screen.dart';

class HistoryScreen extends StatelessWidget {
  const HistoryScreen({super.key});

  void _showClearAllDialog(
    BuildContext context,
    HistoryController c,
    bool isDark,
  ) {
    final theme = Theme.of(context);

    showDialog(
      context: context,
      barrierColor: Colors.black.withOpacity(isDark ? 0.55 : 0.35),
      builder: (_) => Dialog(
        backgroundColor: Colors.transparent,
        insetPadding: const EdgeInsets.symmetric(horizontal: 24),
        child: Container(
          padding: const EdgeInsets.fromLTRB(20, 18, 20, 16),
          decoration: BoxDecoration(
            color: isDark ? theme.colorScheme.surface : Colors.white,
            borderRadius: BorderRadius.circular(16), // 카드 기본 라운드
            border: Border.all(
              color: isDark
                  ? theme.colorScheme.outlineVariant.withOpacity(0.7)
                  : Colors.black.withOpacity(0.08),
              width: 1,
            ),
          ),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Text(
                '전체 삭제',
                style: TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w700,
                  color: isDark ? theme.colorScheme.onSurface : Colors.black,
                ),
              ),
              const SizedBox(height: 8),
              Text(
                '히스토리를 모두 삭제할까요?',
                textAlign: TextAlign.center,
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w400,
                  color: isDark
                      ? theme.colorScheme.onSurface.withOpacity(0.87)
                      : Colors.black87,
                ),
              ),
              const SizedBox(height: 16),
              Row(
                children: [
                  Expanded(
                    child: OutlinedButton(
                      onPressed: () => Navigator.pop(context),
                      style: OutlinedButton.styleFrom(
                        foregroundColor: isDark
                            ? theme.colorScheme.onSurfaceVariant
                            : const Color(0xFF666666),
                        side: BorderSide(
                          color: isDark
                              ? theme.colorScheme.outlineVariant
                              : Colors.black.withOpacity(0.12),
                        ),
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                      child: const Text('취소'),
                    ),
                  ),
                  const SizedBox(width: 10),
                  Expanded(
                    child: ElevatedButton(
                      onPressed: () {
                        Navigator.pop(context);
                        c.clearAll();
                      },
                      style: ElevatedButton.styleFrom(
                        backgroundColor: const Color(0xFFE53935), // ✅ 실무 최빈 삭제색
                        foregroundColor: Colors.white,
                        elevation: 0,
                        shape: RoundedRectangleBorder(
                          borderRadius: BorderRadius.circular(12),
                        ),
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                      child: const Text('삭제'),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    Get.lazyPut<HistoryController>(() => HistoryController());
    final c = Get.find<HistoryController>();
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final bg = isDark
        ? theme.colorScheme.surfaceVariant
        : const Color(0xFFF7F7F7);

    final shell = Get.isRegistered<ShellController>()
        ? Get.find<ShellController>()
        : null;

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
                ? theme.colorScheme.outlineVariant.withOpacity(0.6)
                : Colors.black.withOpacity(0.06),
            width: 1,
          ),
        ),
        leading: IconButton(
          tooltip: '뒤로가기',
          icon: const Icon(PhosphorIconsRegular.caretLeft, size: 32),
          onPressed: () {
            if (Navigator.of(context).canPop()) {
              Navigator.of(context).pop();
              return;
            }
            shell?.setTab(1); // 홈 탭
          },
        ),
        title: const Text(
          'History',
          style: TextStyle(fontSize: 30, fontWeight: FontWeight.w400),
        ),
        centerTitle: true,
        actions: [
          TrashIconButton(
            onPressed: () => _showClearAllDialog(context, c, isDark),
          ),
          SettingsIconButton(
            onPressed: () => Get.to(() => const SettingsScreen()),
          ),
        ],
      ),
      body: SafeArea(
        child: Obx(() {
          if (c.items.isEmpty) {
            return const _EmptyHistory();
          }

          return ListView.separated(
            padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
            itemCount: c.items.length,
            separatorBuilder: (_, __) => const SizedBox(height: 12),
            itemBuilder: (context, index) {
              final item = c.items[index];
              return HistoryListItem(
                item: item,
                onDelete: () => c.removeById(item.id),
                onTap: () {
                  // TODO: Result_UI 연결
                },
              );
            },
          );
        }),
      ),
    );
  }
}

/// ===============================
///  Icon Buttons (Phosphor 통일)
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
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return GestureDetector(
      behavior: HitTestBehavior.opaque, // 터치 영역 안정화(실무 필수)
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) {
        setState(() => _pressed = false);
        widget.onPressed();
      },
      onTapCancel: () => setState(() => _pressed = false),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: 8,
        ), // AppBar action spacing
        child: Icon(
          _pressed ? PhosphorIconsFill.gear : PhosphorIconsRegular.gear,
          size: 32,
          color: isDark
              ? (_pressed
                    ? theme.colorScheme.onSurface
                    : theme.colorScheme.onSurface.withOpacity(0.85))
              : (_pressed ? Colors.black : null),
        ),
      ),
    );
  }
}

class TrashIconButton extends StatefulWidget {
  final VoidCallback onPressed;
  const TrashIconButton({super.key, required this.onPressed});

  @override
  State<TrashIconButton> createState() => _TrashIconButtonState();
}

class _TrashIconButtonState extends State<TrashIconButton> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;

    return GestureDetector(
      behavior: HitTestBehavior.opaque, // 터치 영역 안정화(실무 필수)
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) {
        setState(() => _pressed = false);
        widget.onPressed();
      },
      onTapCancel: () => setState(() => _pressed = false),
      child: Padding(
        padding: const EdgeInsets.symmetric(
          horizontal: 8,
        ), // AppBar action spacing
        child: Icon(
          _pressed ? PhosphorIconsFill.trash : PhosphorIconsRegular.trash,
          size: 32,
          color: isDark
              ? (_pressed ? Colors.red : theme.colorScheme.onSurfaceVariant)
              : (_pressed ? Colors.red : null),
        ),
      ),
    );
  }
}

class _EmptyHistory extends StatelessWidget {
  const _EmptyHistory();

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    return Container(
      color: isDark
          ? theme.colorScheme.surfaceVariant
          : const Color(0xFFF7F7F7),
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(
                PhosphorIconsRegular.clockCounterClockwise,
                size: 44,
                color: theme.colorScheme.onSurface.withOpacity(0.5),
              ),
              const SizedBox(height: 10),
              const Text(
                '히스토리가 비어있어요',
                style: TextStyle(fontWeight: FontWeight.w900, fontSize: 16),
              ),
              const SizedBox(height: 6),
              Text(
                '검증을 실행하면 최근 결과가 여기에 쌓입니다.',
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
