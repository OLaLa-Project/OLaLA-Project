import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';
import '../../shared/storage/local_storage.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool _isDarkMode = false;

  @override
  void initState() {
    super.initState();
    _isDarkMode = Get.isDarkMode;
  }

  Future<void> _toggleDarkMode() async {
    final next = !_isDarkMode;
    setState(() {
      _isDarkMode = next;
    });
    Get.changeThemeMode(next ? ThemeMode.dark : ThemeMode.light);
    await LocalStorage.setDarkMode(next);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final bg = isDark ? theme.colorScheme.surface : const Color(0xFFF7F7F7);

    return Scaffold(
      backgroundColor: bg,
      appBar: AppBar(
        backgroundColor: isDark ? theme.colorScheme.surface : Colors.white,
        foregroundColor: isDark ? theme.colorScheme.onSurface : Colors.black,
        elevation: 0,
        surfaceTintColor: isDark
            ? theme.colorScheme.surface
            : Colors.white, // M3 색 섞임 방지
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
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: const Text(
          'Settings',
          style: TextStyle(fontSize: 30, fontWeight: FontWeight.w400),
        ),
        centerTitle: true,
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _Section(
            title: '일반',
            children: [
              ListTile(
                contentPadding: EdgeInsets.zero,
                title: const Text(
                  '다크 모드',
                  style: TextStyle(fontWeight: FontWeight.w700),
                ),
                trailing: IconButton(
                  icon: Icon(
                    _isDarkMode
                        ? PhosphorIconsRegular.toggleRight
                        : PhosphorIconsRegular.toggleLeft,
                    size: 32,
                    color: isDark
                        ? (_isDarkMode
                              ? theme.colorScheme.primary
                              : theme.colorScheme.outline)
                        : (_isDarkMode ? Colors.blue : Colors.grey),
                  ),
                  onPressed: _toggleDarkMode,
                ),
              ),
              const _Item(
                title: '글자 크기',
                trailing: Icon(PhosphorIconsRegular.caretRight, size: 20),
              ),
              const _Item(
                title: '언어',
                trailing: Icon(PhosphorIconsRegular.caretRight, size: 20),
              ),
            ],
          ),
          const SizedBox(height: 16),
          _Section(
            title: '데이터',
            children: const [
              _Item(
                title: '캐시 삭제',
                trailing: Icon(PhosphorIconsRegular.caretRight, size: 20),
              ),
              _Item(
                title: '앱 정보',
                trailing: Icon(PhosphorIconsRegular.caretRight, size: 20),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _Section extends StatelessWidget {
  final String title;
  final List<Widget> children;

  const _Section({required this.title, required this.children});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: theme.colorScheme.outlineVariant.withOpacity(0.6),
        ),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(title, style: const TextStyle(fontWeight: FontWeight.w900)),
          const SizedBox(height: 10),
          ...children,
        ],
      ),
    );
  }
}

class _Item extends StatelessWidget {
  final String title;
  final Widget trailing;

  const _Item({required this.title, required this.trailing});

  @override
  Widget build(BuildContext context) {
    return ListTile(
      contentPadding: EdgeInsets.zero,
      title: Text(title, style: const TextStyle(fontWeight: FontWeight.w700)),
      trailing: trailing,
      onTap: () {
        // TODO: 각 설정 화면 연결
      },
    );
  }
}
