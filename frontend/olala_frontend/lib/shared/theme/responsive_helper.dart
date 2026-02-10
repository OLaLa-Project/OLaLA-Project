import 'package:flutter/material.dart';

/// 반응형 디자인 헬퍼 클래스
///
/// 화면 크기에 따라 UI 요소의 크기를 자동으로 조정합니다.
/// [BuildContext] 확장 메서드를 통해 `context.responsive`로 접근 가능합니다.
///
/// 사용 예시:
/// ```dart
/// final height = context.responsive.buttonHeightLarge;
/// final fontSize = context.responsive.scaleFontSize(17);
/// ```
class ResponsiveHelper {
  final BuildContext context;

  ResponsiveHelper(this.context);

  // ===== Screen Size =====
  /// 화면 너비
  double get screenWidth => MediaQuery.of(context).size.width;

  /// 화면 높이
  double get screenHeight => MediaQuery.of(context).size.height;

  /// 화면의 짧은 쪽 길이
  double get shortestSide => MediaQuery.of(context).size.shortestSide;

  /// 화면의 긴 쪽 길이
  double get longestSide => MediaQuery.of(context).size.longestSide;

  // ===== Device Type Detection =====
  /// 소형 디바이스 여부 (화면 너비 < 360px)
  bool get isSmallDevice => screenWidth < 360;

  /// 중형 디바이스 여부 (360px <= 화면 너비 < 414px)
  bool get isMediumDevice => screenWidth >= 360 && screenWidth < 414;

  /// 대형 디바이스 여부 (화면 너비 >= 414px)
  bool get isLargeDevice => screenWidth >= 414;

  /// 태블릿 여부 (화면의 짧은 쪽 >= 600px)
  bool get isTablet => shortestSide >= 600;

  // ===== Scale Factor =====
  /// 기준 화면 너비 (iPhone 13 기준)
  static const double _baseWidth = 390.0;

  /// 화면 크기 기반 스케일 팩터 (0.85 ~ 1.15 범위로 제한)
  double get scaleFactor => (screenWidth / _baseWidth).clamp(0.85, 1.15);

  // ===== Button Heights =====
  /// 대형 버튼 높이 (기본: 58px)
  double get buttonHeightLarge => _scaleSize(58.0);

  /// 중형 버튼 높이 (기본: 56px)
  double get buttonHeight => _scaleSize(56.0);

  /// 소형 버튼 높이 (기본: 48px)
  double get buttonHeightSmall => _scaleSize(48.0);

  // ===== Border Radius =====
  /// 대형 radius (기본: 28px)
  double get radius28 => _scaleSize(28.0);

  /// 중형 radius (기본: 20px)
  double get radius20 => _scaleSize(20.0);

  /// 소형 radius (기본: 16px)
  double get radius16 => _scaleSize(16.0);

  /// 최소 radius (기본: 12px)
  double get radius12 => _scaleSize(12.0);

  /// 초소형 radius (기본: 8px)
  double get radius8 => _scaleSize(8.0);

  // ===== Spacing =====
  /// 초소형 간격 (기본: 4px)
  double get spacing4 => _scaleSize(4.0);

  /// 소형 간격 (기본: 8px)
  double get spacing8 => _scaleSize(8.0);

  /// 중소형 간격 (기본: 12px)
  double get spacing12 => _scaleSize(12.0);

  /// 중형 간격 (기본: 16px)
  double get spacing16 => _scaleSize(16.0);

  /// 중대형 간격 (기본: 20px)
  double get spacing20 => _scaleSize(20.0);

  /// 대형 간격 (기본: 24px)
  double get spacing24 => _scaleSize(24.0);

  /// 초대형 간격 (기본: 32px)
  double get spacing32 => _scaleSize(32.0);

  // ===== Helper Methods =====
  /// 폰트 크기를 화면 크기에 맞게 조정
  ///
  /// [baseFontSize] 기본 폰트 크기
  /// 반환값: 스케일 조정된 폰트 크기
  double scaleFontSize(double baseFontSize) {
    return _scaleSize(baseFontSize);
  }

  /// 크기를 화면 크기에 맞게 조정 (내부 메서드)
  double _scaleSize(double baseSize) {
    // 태블릿은 스케일을 제한적으로 적용
    if (isTablet) {
      return baseSize * 1.05;
    }
    return baseSize * scaleFactor;
  }

  /// 최소/최대값을 지정하여 크기 조정
  ///
  /// [baseSize] 기본 크기
  /// [minSize] 최소 크기
  /// [maxSize] 최대 크기
  double scaleWithConstraints(
    double baseSize, {
    double? minSize,
    double? maxSize,
  }) {
    final scaled = _scaleSize(baseSize);
    return scaled.clamp(minSize ?? 0.0, maxSize ?? double.infinity);
  }

  /// 가로 패딩 (화면 가장자리 여백, 기본: 16px)
  double get horizontalPadding => _scaleSize(16.0);

  /// 세로 패딩 (기본: 16px)
  double get verticalPadding => _scaleSize(16.0);

  /// 안전 영역 상단 패딩
  double get safeAreaTop => MediaQuery.of(context).padding.top;

  /// 안전 영역 하단 패딩
  double get safeAreaBottom => MediaQuery.of(context).padding.bottom;
}

/// [BuildContext] 확장 메서드
///
/// `context.responsive`로 [ResponsiveHelper]에 접근할 수 있습니다.
extension ResponsiveExtension on BuildContext {
  /// 반응형 헬퍼 인스턴스
  ResponsiveHelper get responsive => ResponsiveHelper(this);
}
