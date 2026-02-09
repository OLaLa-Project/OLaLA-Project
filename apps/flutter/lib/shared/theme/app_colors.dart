import 'package:flutter/material.dart';

/// Shared color tokens used by a few UI widgets.
///
/// Prefer using `Theme.of(context).colorScheme` when possible; these are
/// lightweight defaults aligned with `AppTheme` for legacy/shared widgets.
class AppColors {
  static const Color primary = Color(0xFF4683F6);

  static const Color surface = Colors.white;
  static const Color textPrimary = Color(0xFF1F1F1F);
  static const Color border = Color(0xFFE6E9EF);

  const AppColors._();
}

