import 'package:flutter/material.dart';
import 'app/app.dart';
import 'shared/storage/local_storage.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  final isDarkMode = await LocalStorage.getDarkMode();
  final themeMode = (isDarkMode ?? false) ? ThemeMode.dark : ThemeMode.light;

  runApp(OLaLAApp(initialThemeMode: themeMode));
}
