import 'package:flutter/foundation.dart';

/// 환경 설정 클래스
/// 개발/프로덕션 환경에 따라 다른 설정을 제공합니다.
class Env {
  Env._();

  /// API 베이스 URL
  /// - 개발: localhost:8080
  /// - 프로덕션: 실제 배포 서버 URL
  static String get apiBaseUrl {
    if (kDebugMode) {
      // iOS 시뮬레이터/Android 에뮬레이터에서 localhost 접근
      if (defaultTargetPlatform == TargetPlatform.android) {
        return 'http://10.0.2.2:8080'; // Android 에뮬레이터
      }
      return 'http://localhost:8080'; // iOS 시뮬레이터 또는 실제 기기
    } else {
      // 프로덕션 환경 (Docker Compose 실행 시 Release 모드일 수 있음 -> Localhost로 지향)
      return 'http://localhost:8080';
    }
  }

  /// API 타임아웃 설정 (초)
  static const int connectTimeout = 30;
  static const int receiveTimeout = 30;
  static const int sendTimeout = 30;

  /// 로그 활성화 여부
  static bool get enableApiLog => kDebugMode;

  /// 앱 버전
  static const String appVersion = '1.0.0';

  /// 기타 환경 설정
  static const String appName = 'OLaLA';
  static const String appDescription = '멀티 에이전트 기반 가짜뉴스 판독 서비스';
}
