import '../models/daily_issue.dart';
import '../models/chat_message.dart';
import 'issue_repository.dart';

class MockIssueRepository implements IssueRepository {
  @override
  Future<DailyIssue?> getTodayIssue() async {
    // 네트워크 지연 시뮬레이션
    await Future.delayed(const Duration(milliseconds: 500));

    final now = DateTime.now();
    final dateStr = '${now.year}${now.month.toString().padLeft(2, '0')}${now.day.toString().padLeft(2, '0')}';

    return DailyIssue(
      id: 'issue_$dateStr',
      title: '2025년 AI 윤리 규제안, 국회 본회의 통과',
      summary: '인공지능 개발 및 활용에 대한 윤리적 기준을 명시한 법안이 국회를 통과했습니다. 이번 법안은 AI 시스템의 투명성, 설명 가능성, 공정성을 강화하는 내용을 담고 있습니다.',
      content: '''국회 본회의에서 인공지능 개발 및 활용에 대한 윤리 기준을 담은 법안이 통과됐다. 이번 법안은 AI 시스템의 투명성과 설명 가능성, 공정성 확보를 핵심 원칙으로 제시하며, 고위험 영역에서의 책임성을 강화하는 내용을 포함한다.

정부는 해당 법안이 시행되면 공공 부문과 민간 기업의 AI 활용 전반에 걸쳐 최소한의 윤리 가이드라인이 마련될 것으로 기대하고 있다. 특히 데이터 편향, 차별적 결과, 개인정보 보호 등 사회적 문제에 대한 예방 조치가 강화된다.

업계에서는 규제 준수 비용과 개발 프로세스 변화에 대한 우려와 함께, 장기적으로는 신뢰 확보와 시장 확장에 도움이 될 수 있다는 의견이 함께 나온다. 일부 기업들은 이미 내부 윤리 위원회 설치와 영향 평가 프로세스를 도입하는 등 선제 대응에 나서고 있다.

향후 시행령 및 세부 지침 마련 과정에서 산업계·학계·시민단체 의견 수렴이 이뤄질 예정이다. 법안의 실효성을 높이기 위해 구체적 평가 기준과 위반 시 제재 수준에 대한 논의도 이어질 전망이다.''',
      category: '정치',
      participantCount: 127,
      publishedAt: DateTime.now().subtract(const Duration(hours: 2)),
    );
  }

  @override
  Future<List<ChatMessage>> getChatHistory(String issueId, {int limit = 50}) async {
    // 네트워크 지연 시뮬레이션
    await Future.delayed(const Duration(milliseconds: 300));

    return [
      ChatMessage(
        id: 'msg1',
        userId: 'user123',
        username: '익명123',
        content: '드디어 AI 규제법이 통과되었네요!',
        timestamp: DateTime.now().subtract(const Duration(minutes: 5)),
        isMine: false,
        reactionCount: 3,
        isReactedByMe: false,
      ),
      ChatMessage(
        id: 'msg2',
        userId: 'user456',
        username: '익명456',
        content: '이번 법안이 실제로 어떤 영향을 미칠까요?',
        timestamp: DateTime.now().subtract(const Duration(minutes: 4)),
        isMine: false,
        reactionCount: 1,
        isReactedByMe: false,
      ),
      ChatMessage(
        id: 'msg3',
        userId: 'user789',
        username: '익명789',
        content: 'AI 개발사들이 따라야 할 기준이 명확해졌다는 점에서 긍정적인 것 같습니다.',
        timestamp: DateTime.now().subtract(const Duration(minutes: 3)),
        isMine: false,
        reactionCount: 5,
        isReactedByMe: false,
      ),
    ];
  }
}
