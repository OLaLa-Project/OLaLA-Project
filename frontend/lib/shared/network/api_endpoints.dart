import 'package:flutter/foundation.dart';

/// API 엔드포인트 상수
class ApiEndpoints {
  // Base URLs (dart-define로 환경별 주입 가능)
  static const String _defaultApiBase = 'http://localhost:8000/v1';

  static const String _apiBaseEnv = String.fromEnvironment(
    'API_BASE',
    defaultValue: _defaultApiBase,
  );
  static const String _wsBaseEnv = String.fromEnvironment(
    'WS_BASE',
    defaultValue: '',
  );
  static const String _publicWebBaseEnv = String.fromEnvironment(
    'PUBLIC_WEB_BASE',
    defaultValue: '',
  );

  static final String apiBase = _resolveApiBase();
  static final String wsBase = _resolveWsBase();
  static final String publicWebBase = _publicWebBaseEnv;

  // Issue endpoints
  static const String todayIssue = '/issues/today';
  static const String issueDetail = '/issues'; // GET /issues/{id}

  // Chat endpoints
  static const String chatHistory =
      '/chat/messages'; // GET /chat/messages/{issueId}
  static const String sendMessage =
      '/chat/messages'; // POST /chat/messages/{issueId}
  static const String toggleReaction =
      '/chat/reactions'; // POST /chat/reactions

  // WebSocket
  static String chatWebSocket(String issueId) => '$wsBase/chat/$issueId';

  /// API_BASE가 상대 경로('/v1')인 경우 브라우저 origin으로 절대 URL 생성
  static String _resolveApiBase() {
    if (_apiBaseEnv.startsWith('http://') ||
        _apiBaseEnv.startsWith('https://')) {
      return _apiBaseEnv;
    }
    // 상대 경로: 웹에서 브라우저 origin 사용
    if (kIsWeb) {
      final origin = Uri.base.origin; // e.g. https://xxx.ngrok-free.dev
      return '$origin${_apiBaseEnv}';
    }
    return _defaultApiBase;
  }

  static String _resolveWsBase() {
    // 1. 명시적 WS_BASE가 있으면 사용
    if (_wsBaseEnv.isNotEmpty) {
      return _adjustWsSchemeForWeb(_wsBaseEnv);
    }

    // 2. API_BASE가 상대 경로('/v1')이면 브라우저 origin에서 추론
    if (!_apiBaseEnv.startsWith('http://') &&
        !_apiBaseEnv.startsWith('https://')) {
      if (kIsWeb) {
        final scheme = Uri.base.scheme == 'https' ? 'wss' : 'ws';
        return '$scheme://${Uri.base.host}:${Uri.base.port}${_apiBaseEnv}';
      }
      return 'ws://localhost:8000/v1';
    }

    // 3. HTTP URL → WS URL 변환
    final inferred = _inferWsBase(_apiBaseEnv);
    return _adjustWsSchemeForWeb(inferred);
  }

  static String _adjustWsSchemeForWeb(String wsUrl) {
    if (kIsWeb &&
        Uri.base.scheme.toLowerCase() == 'https' &&
        wsUrl.startsWith('ws://')) {
      return wsUrl.replaceFirst('ws://', 'wss://');
    }
    return wsUrl;
  }

  static String _inferWsBase(String apiBaseValue) {
    if (apiBaseValue.startsWith('https://')) {
      return apiBaseValue.replaceFirst('https://', 'wss://');
    }
    if (apiBaseValue.startsWith('http://')) {
      return apiBaseValue.replaceFirst('http://', 'ws://');
    }
    return 'ws://localhost:8000/v1';
  }
}
