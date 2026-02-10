import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:get/get.dart';

import 'bindings/initial_binding.dart';
import 'routes.dart';
import 'theme/app_theme.dart';

import '../features/splash/splash_screen.dart';
import '../features/onboarding/onboarding_screen.dart';
import '../features/shell/shell_screen.dart';
import '../features/issue_chat/services/chat_join_link.dart';
import '../features/issue_chat/web_chat_entry_screen.dart';

import 'package:device_preview/device_preview.dart';

class OLaLAApp extends StatefulWidget {
  final ThemeMode initialThemeMode;

  const OLaLAApp({super.key, this.initialThemeMode = ThemeMode.light});

  @override
  State<OLaLAApp> createState() => _OLaLAAppState();
}

class _OLaLAAppState extends State<OLaLAApp> {
  String _resolveInitialRoute() {
    if (!kIsWeb) return AppRoutes.splash;

    final issueId = Uri.base.queryParameters['issueId']?.trim();
    if (issueId != null && issueId.isNotEmpty) {
      return AppRoutes.webChat;
    }

    final segments = Uri.base.pathSegments
        .where((segment) => segment.trim().isNotEmpty)
        .toList();
    final lastSegment = segments.isNotEmpty ? segments.last : '';
    if (lastSegment == ChatJoinLink.webChatPath) {
      return AppRoutes.webChat;
    }

    return AppRoutes.splash;
  }

  @override
  Widget build(BuildContext context) {
    return GetMaterialApp(
      useInheritedMediaQuery: true,
      locale: DevicePreview.locale(context),
      builder: DevicePreview.appBuilder,
      title: '오늘의 이슈',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: widget.initialThemeMode,
      initialBinding: InitialBinding(),
      initialRoute: _resolveInitialRoute(),
      getPages: [
        GetPage(name: AppRoutes.splash, page: () => const SplashScreen()),
        GetPage(
          name: AppRoutes.onboarding,
          page: () => const OnboardingScreen(),
        ),
        GetPage(name: AppRoutes.webChat, page: () => const WebChatEntryScreen()),
        GetPage(name: AppRoutes.shell, page: () => const ShellScreen()),
        // ✅ Coach 라우트 제거 (오버레이로 변경)
      ],
    );
  }
}
