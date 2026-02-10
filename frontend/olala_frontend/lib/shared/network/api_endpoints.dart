import 'package:flutter/foundation.dart';

/// API 엔드포인트 상수
class ApiEndpoints {
  // Base URLs (dart-define로 환경별 주입 가능)
  static const String _defaultApiBase = 'http://localhost:8000/v1';
  static const String _defaultWsBase = 'ws://localhost:8000/v1';

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

  static final String apiBase = _apiBaseEnv;
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

  static String _resolveWsBase() {
    final configured = _wsBaseEnv.isNotEmpty
        ? _wsBaseEnv
        : _inferWsBase(_apiBaseEnv);

    if (kIsWeb &&
        Uri.base.scheme.toLowerCase() == 'https' &&
        configured.startsWith('ws://')) {
      return configured.replaceFirst('ws://', 'wss://');
    }

    return configured;
  }

  static String _inferWsBase(String apiBaseValue) {
    if (apiBaseValue.startsWith('https://')) {
      return apiBaseValue.replaceFirst('https://', 'wss://');
    }
    if (apiBaseValue.startsWith('http://')) {
      return apiBaseValue.replaceFirst('http://', 'ws://');
    }
    return _defaultWsBase;
  }
}
