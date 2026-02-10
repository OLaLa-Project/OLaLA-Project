import 'evidence_card.dart';

/// 검증 결과 데이터
class VerificationResult {
  final String verdict;        // 'true', 'false', 'mixed', 'unverified'
  final double confidence;      // 0.0 ~ 1.0
  final String headline;        // 결과 헤드라인
  final String reason;          // 결과 요약/이유
  final List<EvidenceCard> evidenceCards;  // 근거 카드 리스트

  VerificationResult({
    required this.verdict,
    required this.confidence,
    required this.headline,
    required this.reason,
    required this.evidenceCards,
  });

  factory VerificationResult.fromJson(Map<String, dynamic> json) {
    return VerificationResult(
      verdict: json['verdict'] ?? 'unverified',
      confidence: (json['confidence'] ?? 0.0).toDouble(),
      headline: json['headline'] ?? '',
      reason: json['reason'] ?? '',
      evidenceCards: (json['evidence_cards'] as List<dynamic>?)
              ?.map((e) => EvidenceCard.fromJson(e))
              .toList() ??
          [],
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'verdict': verdict,
      'confidence': confidence,
      'headline': headline,
      'reason': reason,
      'evidence_cards': evidenceCards.map((e) => e.toJson()).toList(),
    };
  }
}
