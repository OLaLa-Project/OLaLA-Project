import 'package:flutter/material.dart';
import 'package:get/get.dart';

import 'bindings/initial_binding.dart';
import 'routes.dart';
import 'theme/app_theme.dart';

import '../features/splash/splash_screen.dart';
import '../features/onboarding/onboarding_screen.dart';
import '../features/shell/shell_screen.dart';
import '../features/verify/presentation/result_screen.dart';
import '../features/verify/presentation/result_controller.dart';

class OLaLAApp extends StatelessWidget {
  const OLaLAApp({super.key});

  @override
  Widget build(BuildContext context) {
    return GetMaterialApp(
      debugShowCheckedModeBanner: false,
      theme: AppTheme.light(),
      initialBinding: InitialBinding(),
      initialRoute: AppRoutes.splash,
      getPages: [
        GetPage(name: AppRoutes.splash, page: () => const SplashScreen()),
        GetPage(
          name: AppRoutes.onboarding,
          page: () => const OnboardingScreen(),
        ),
        GetPage(name: AppRoutes.shell, page: () => const ShellScreen()),
        GetPage(
          name: AppRoutes.result,
          page: () => const ResultScreen(),
          binding: BindingsBuilder(() {
            // Lazy put controller if not already present, or rely on bindings
            Get.lazyPut(() => ResultController()); 
          }),
        ),
      ],
    );
  }
}
