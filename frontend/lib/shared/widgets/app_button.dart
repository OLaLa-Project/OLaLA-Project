import 'package:flutter/material.dart';
import '../theme/responsive_helper.dart';
import '../theme/app_colors.dart';

/// 반응형 앱 버튼
///
/// 화면 크기에 따라 높이, 폰트 크기, BorderRadius가 자동 조정됩니다.
///
/// 사용 예시:
/// ```dart
/// AppButton(
///   text: '검증 시작',
///   onPressed: () {},
/// )
/// ```
class AppButton extends StatelessWidget {
  /// 버튼 텍스트
  final String text;

  /// 클릭 이벤트
  final VoidCallback? onPressed;

  /// 로딩 상태
  final bool isLoading;

  /// 버튼 스타일 (primary, secondary, outlined)
  final AppButtonStyle buttonStyle;

  /// 버튼 크기 (large, medium, small)
  final AppButtonSize size;

  /// 전체 너비 사용 여부
  final bool fullWidth;

  const AppButton({
    super.key,
    required this.text,
    this.onPressed,
    this.isLoading = false,
    this.buttonStyle = AppButtonStyle.primary,
    this.size = AppButtonSize.large,
    this.fullWidth = true,
  });

  @override
  Widget build(BuildContext context) {
    final responsive = context.responsive;

    // 버튼 높이 결정
    final double height = switch (size) {
      AppButtonSize.large => responsive.buttonHeightLarge,
      AppButtonSize.medium => responsive.buttonHeight,
      AppButtonSize.small => responsive.buttonHeightSmall,
    };

    // 폰트 크기
    final double fontSize = switch (size) {
      AppButtonSize.large => responsive.scaleFontSize(17),
      AppButtonSize.medium => responsive.scaleFontSize(15),
      AppButtonSize.small => responsive.scaleFontSize(14),
    };

    // BorderRadius
    final double radius = switch (size) {
      AppButtonSize.large => responsive.radius28,
      AppButtonSize.medium => responsive.radius20,
      AppButtonSize.small => responsive.radius16,
    };

    // 버튼 스타일
    final ButtonStyle style = switch (buttonStyle) {
      AppButtonStyle.primary => ElevatedButton.styleFrom(
          backgroundColor: AppColors.primary,
          foregroundColor: Colors.white,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radius),
          ),
          textStyle: TextStyle(
            fontSize: fontSize,
            fontWeight: FontWeight.w700,
          ),
        ),
      AppButtonStyle.secondary => ElevatedButton.styleFrom(
          backgroundColor: AppColors.surface,
          foregroundColor: AppColors.textPrimary,
          elevation: 0,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radius),
            side: BorderSide(color: AppColors.border),
          ),
          textStyle: TextStyle(
            fontSize: fontSize,
            fontWeight: FontWeight.w700,
          ),
        ),
      AppButtonStyle.outlined => OutlinedButton.styleFrom(
          foregroundColor: AppColors.primary,
          side: BorderSide(color: AppColors.primary, width: 2),
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(radius),
          ),
          textStyle: TextStyle(
            fontSize: fontSize,
            fontWeight: FontWeight.w700,
          ),
        ),
    };

    Widget button = SizedBox(
      height: height,
      width: fullWidth ? double.infinity : null,
      child: buttonStyle == AppButtonStyle.outlined
          ? OutlinedButton(
              style: style,
              onPressed: isLoading ? null : onPressed,
              child: _buildChild(fontSize),
            )
          : ElevatedButton(
              style: style,
              onPressed: isLoading ? null : onPressed,
              child: _buildChild(fontSize),
            ),
    );

    return button;
  }

  Widget _buildChild(double fontSize) {
    if (isLoading) {
      return SizedBox(
        width: fontSize * 1.2,
        height: fontSize * 1.2,
        child: const CircularProgressIndicator(
          strokeWidth: 2,
          valueColor: AlwaysStoppedAnimation(Colors.white),
        ),
      );
    }

    return Text(text);
  }
}

/// 버튼 스타일
enum AppButtonStyle {
  /// Primary (파란색 배경)
  primary,

  /// Secondary (흰색 배경, 보더)
  secondary,

  /// Outlined (테두리만)
  outlined,
}

/// 버튼 크기
enum AppButtonSize {
  /// Large (58px)
  large,

  /// Medium (56px)
  medium,

  /// Small (48px)
  small,
}
