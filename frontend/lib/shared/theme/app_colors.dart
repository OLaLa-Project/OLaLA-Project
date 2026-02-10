import 'package:flutter/material.dart';

/// 앱 전체에서 사용하는 색상 정의
///
/// [AppTheme]과 일관성을 유지하며, 위젯에서 직접 참조 가능한 색상 상수를 제공합니다.
class AppColors {
  // Private constructor to prevent instantiation
  AppColors._();

  // ===== Brand Colors =====
  /// 브랜드 Primary 색상 (파란색)
  static const Color primary = Color(0xFF4683F6);

  // ===== Surface Colors =====
  /// 기본 표면 색상 (흰색)
  static const Color surface = Colors.white;

  /// 배경 색상 (연한 회색)
  static const Color background = Color(0xFFF7F7F7);

  /// 표면 변형 색상 (연한 회색)
  static const Color surfaceVariant = Color(0xFFF7F7F7);

  // ===== Text Colors =====
  /// 주요 텍스트 색상 (진한 회색)
  static const Color textPrimary = Color(0xFF1F1F1F);

  /// 보조 텍스트 색상 (중간 회색)
  static const Color textSecondary = Color(0xFF5F6570);

  /// 비활성 텍스트 색상 (연한 회색)
  static const Color textDisabled = Color(0xFF667085);

  // ===== Border Colors =====
  /// 기본 보더 색상
  static const Color border = Color(0xFFE6E9EF);

  /// 보더 변형 색상
  static const Color borderVariant = Color(0xFF2B2B2B);

  // ===== Status Colors =====
  /// 성공 색상 (초록색)
  static const Color success = Color(0xFF34C759);

  /// 성공 배경 색상
  static const Color successBg = Color(0xFFE8F9EA);

  /// 오류 색상 (빨간색)
  static const Color error = Color(0xFFEF4444);

  /// 오류 배경 색상
  static const Color errorBg = Color(0xFFFFEAEA);

  /// 경고 색상 (주황색)
  static const Color warning = Color(0xFFF59E0B);

  /// 경고 배경 색상
  static const Color warningBg = Color(0xFFFFF4E6);

  // ===== Accent Colors =====
  /// Accent 색상 (연한 파란색)
  static const Color accent = Color(0xFFE6ECFF);

  /// Accent 강조 색상
  static const Color accentStrong = Color(0xFF3478F6);

  // ===== Dark Mode Colors =====
  /// 다크 모드 표면 색상
  static const Color darkSurface = Color(0xFF000000);

  /// 다크 모드 표면 변형
  static const Color darkSurfaceVariant = Color(0xFF161616);

  /// 다크 모드 텍스트
  static const Color darkTextPrimary = Color(0xFFF2F2F2);

  /// 다크 모드 보조 텍스트
  static const Color darkTextSecondary = Color(0xFFB8B8B8);
}
