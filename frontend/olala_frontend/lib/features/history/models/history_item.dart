class HistoryItem {
  final String id;
  final String inputSummary; // 입력 요약
  final String resultLabel; // TRUE/FALSE/MIXED 등
  final DateTime timestamp;

  HistoryItem({
    required this.id,
    required this.inputSummary,
    required this.resultLabel,
    required this.timestamp,
  });
}
