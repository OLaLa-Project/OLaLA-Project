import '../../app/env.dart';

/// API 엔드포인트 상수
class ApiEndpoints {
  // Base URLs (dart-define 또는 env 파일로 환경별 주입)
  static String get apiBase => AppEnv.apiBase;
  static String get wsBase => AppEnv.wsBase;

  // Issue endpoints
  static const String todayIssue = '/issues/today';
  static const String issueDetail = '/issues'; // GET /issues/{id}

  // Chat endpoints
  static const String chatHistory = '/chat/messages'; // GET /chat/messages/{issueId}
  static const String sendMessage = '/chat/messages'; // POST /chat/messages/{issueId}
  static const String toggleReaction = '/chat/reactions'; // POST /chat/reactions

  // WebSocket
  static String chatWebSocket(String issueId) => '$wsBase/chat/$issueId';
}
