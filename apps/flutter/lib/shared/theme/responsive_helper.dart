import 'package:flutter/widgets.dart';

/// Minimal responsive helper used by shared widgets.
///
/// NOTE: This is intentionally lightweight (no dependencies) and only exposes
/// the tokens currently consumed by `AppButton`.
class ResponsiveHelper {
  final double width;
  final double height;
  final double _scale;

  ResponsiveHelper._({
    required this.width,
    required this.height,
    required double scale,
  }) : _scale = scale;

  factory ResponsiveHelper.of(BuildContext context) {
    final size = MediaQuery.sizeOf(context);
    // Base width chosen to keep a sane scale across common phones.
    const baseWidth = 390.0;
    final scale = (size.width / baseWidth).clamp(0.85, 1.20).toDouble();
    return ResponsiveHelper._(width: size.width, height: size.height, scale: scale);
  }

  double scaleFontSize(double size) => size * _scale;

  double get buttonHeightLarge => 58.0 * _scale;
  double get buttonHeight => 56.0 * _scale;
  double get buttonHeightSmall => 48.0 * _scale;

  double get radius28 => 28.0 * _scale;
  double get radius20 => 20.0 * _scale;
  double get radius16 => 16.0 * _scale;
}

extension ResponsiveBuildContext on BuildContext {
  ResponsiveHelper get responsive => ResponsiveHelper.of(this);
}

