import 'package:flutter/material.dart';

class SettingsScreen extends StatelessWidget {
  const SettingsScreen({super.key});

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Color(0xFFF7F7F7),
      appBar: AppBar(title: const Text('설정'), centerTitle: true),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _Section(
            title: '일반',
            children: const [
              _Item(title: '다크 모드', trailing: Icon(Icons.chevron_right)),
              _Item(title: '글자 크기', trailing: Icon(Icons.chevron_right)),
              _Item(title: '언어', trailing: Icon(Icons.chevron_right)),
            ],
          ),
          const SizedBox(height: 16),
          _Section(
            title: '데이터',
            children: const [
              _Item(title: '캐시 삭제', trailing: Icon(Icons.chevron_right)),
              _Item(title: '앱 정보', trailing: Icon(Icons.chevron_right)),
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
