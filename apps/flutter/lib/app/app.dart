import 'package:flutter/material.dart';
import 'package:get/get.dart';

import 'bindings/initial_binding.dart';
import 'routes.dart';
import 'theme/app_theme.dart';

import '../features/splash/splash_screen.dart';
import '../features/onboarding/onboarding_screen.dart';
import '../features/shell/shell_screen.dart';

class OLaLAApp extends StatelessWidget {
  final ThemeMode initialThemeMode;

  const OLaLAApp({
    super.key,
    this.initialThemeMode = ThemeMode.light,
  });

  @override
  Widget build(BuildContext context) {
    return GetMaterialApp(
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      darkTheme: AppTheme.dark(),
      themeMode: initialThemeMode,
      initialBinding: InitialBinding(),
      initialRoute: AppRoutes.splash,
      getPages: [
        GetPage(name: AppRoutes.splash, page: () => const SplashScreen()),
        GetPage(
          name: AppRoutes.onboarding,
          page: () => const OnboardingScreen(),
        ),
        GetPage(name: AppRoutes.shell, page: () => const ShellScreen()),
        // ✅ Coach 라우트 제거 (오버레이로 변경)
      ],
    );
  }
}
