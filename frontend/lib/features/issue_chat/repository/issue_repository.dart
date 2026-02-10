import '../models/daily_issue.dart';
import '../models/chat_message.dart';

abstract class IssueRepository {
  /// 오늘의 이슈 조회
  Future<DailyIssue?> getTodayIssue();

  /// 이슈 ID로 단건 조회
  Future<DailyIssue?> getIssueById(String issueId);

  /// 채팅 히스토리 조회
  Future<List<ChatMessage>> getChatHistory(String issueId, {int limit = 50});
}
