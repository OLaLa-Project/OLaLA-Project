import 'package:flutter/material.dart';

class AppTheme {
  static const Color _brand = Color(0xFF4683F6);

  static ThemeData light() {
    final colorScheme =
        ColorScheme.fromSeed(
          seedColor: _brand,
          brightness: Brightness.light,
        ).copyWith(
          primary: _brand,
          surface: Colors.white,
          surfaceVariant: const Color(0xFFF7F7F7),
          onSurface: const Color(0xFF1F1F1F),
          onSurfaceVariant: const Color(0xFF5F6570),
          outlineVariant: const Color(0xFFE6E9EF),
        );

    return ThemeData(
      useMaterial3: false,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: const Color(0xFFF7F7F7),
    );
  }

  static ThemeData dark() {
    final colorScheme =
        ColorScheme.fromSeed(
          seedColor: _brand,
          brightness: Brightness.dark,
        ).copyWith(
          primary: _brand,
          surface: const Color(0xFF000000),
          surfaceVariant: const Color(0xFF000000),
          surfaceContainerHighest: const Color(0xFF161616),
          onSurface: const Color(0xFFF2F2F2),
          onSurfaceVariant: const Color(0xFFB8B8B8),
          outlineVariant: const Color(0xFF2B2B2B),
        );

    return ThemeData(
      brightness: Brightness.dark,
      useMaterial3: false,
      colorScheme: colorScheme,
      scaffoldBackgroundColor: const Color(0xFF000000),
    );
  }
}
