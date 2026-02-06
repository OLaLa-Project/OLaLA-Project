
import 'package:flutter/foundation.dart';

class ApiEndpoints {
  // Base URL
  // In development (local), we use localhost.
  // When running in Docker/Emulator, this might need adjustment,
  // but ApiClient handles the base usually.
  // Here we define the path prefixes.

  static const String apiBase = '/api';

  // Issue Endpoints
  static const String todayIssue = '/issues/today';
  static const String chatHistory = '/chat/messages';

  // WebSocket
  static String chatWebSocket(String issueId) {
    // Determine WS protocol based on environment or hardcode for dev
    // For localhost:8080
    // If running on web, we can use relative if supported, or absolute.
    // For MVP/Docker, let's assume ws://localhost:8080/api/ws/...
    
    // Note: In a real app, you'd want to derive this from the base API URL.
    // simpler for now:
    const String baseUrl = 'ws://localhost:8080'; 
    // Or match the http client base url logic if possible, but WS is distinct.
    
    return '$baseUrl/api/ws/issues/$issueId/chat';
  }
}
