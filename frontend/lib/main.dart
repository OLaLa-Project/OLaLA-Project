import 'package:flutter/material.dart';
import 'app/app.dart';
import 'shared/storage/local_storage.dart';
import 'package:device_preview/device_preview.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final isDarkMode = await LocalStorage.getDarkMode();
  final themeMode = (isDarkMode ?? false) ? ThemeMode.dark : ThemeMode.light;

  runApp(
    DevicePreview(
      enabled: true, // Linux Desktop에서 항상 모바일 프레임 보이게 설정
      builder: (context) => OLaLAApp(initialThemeMode: themeMode),
    ),
  );
}
