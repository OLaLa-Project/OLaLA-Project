import '../../verify/models/evidence_card.dart';

class HistoryItem {
  final String id;
  final String inputSummary; // List View Summary
  final String resultLabel; // TRUE/FALSE/MIXED/UNVERIFIED
  final DateTime timestamp;

  // Restore Data
  final double confidence;
  final String headline;
  final String summary; // Full Result Summary
  final String userQuery;
  final List<EvidenceCard> evidenceCards;

  HistoryItem({
    required this.id,
    required this.inputSummary,
    required this.resultLabel,
    required this.timestamp,
    this.confidence = 0.0,
    this.headline = '',
    this.summary = '',
    this.userQuery = '',
    this.evidenceCards = const [],
  });

  factory HistoryItem.fromJson(Map<String, dynamic> json) {
    return HistoryItem(
      id: json['id'] as String,
      inputSummary: json['inputSummary'] as String,
      resultLabel: json['resultLabel'] as String,
      timestamp: DateTime.parse(json['timestamp'] as String),
      confidence: (json['confidence'] as num?)?.toDouble() ?? 0.0,
      headline: json['headline'] as String? ?? '',
      summary: json['summary'] as String? ?? '',
      userQuery: json['userQuery'] as String? ?? '',
      evidenceCards: (json['evidenceCards'] as List<dynamic>?)
              ?.map((e) => EvidenceCard.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'inputSummary': inputSummary,
      'resultLabel': resultLabel,
      'timestamp': timestamp.toIso8601String(),
      'confidence': confidence,
      'headline': headline,
      'summary': summary,
      'userQuery': userQuery,
      'evidenceCards': evidenceCards.map((e) => e.toJson()).toList(),
    };
  }
}
