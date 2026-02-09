class VerificationResult {
  const VerificationResult({
    required this.label,
    required this.confidence,
    required this.summary,
    required this.rationale,
    required this.citations,
    required this.counterEvidence,
    required this.limitations,
    required this.recommendedNextSteps,
    required this.riskFlags,
    this.analysisId,
    this.headline,
    this.explanation,
  });

  final String label;
  final double confidence;
  final String summary;
  final List<String> rationale;
  final List<Map<String, dynamic>> citations;
  final List<Map<String, dynamic>> counterEvidence;
  final List<String> limitations;
  final List<String> recommendedNextSteps;
  final List<String> riskFlags;
  final String? analysisId;
  final String? headline;
  final String? explanation;

  factory VerificationResult.fromJson(Map<String, dynamic> json) {
    final confidenceRaw = json['confidence'];
    final confidence = _normalizeConfidence(confidenceRaw);

    final summary = _asString(json['summary']);
    final headline = _asString(json['headline']);
    final explanation = _asString(json['explanation']);

    return VerificationResult(
      label: _normalizeLabel(json['label']),
      confidence: confidence,
      summary: summary,
      rationale: _stringList(json['rationale']),
      citations: _mapList(json['citations']),
      counterEvidence: _mapList(json['counter_evidence']),
      limitations: _stringList(json['limitations']),
      recommendedNextSteps: _stringList(json['recommended_next_steps']),
      riskFlags: _stringList(json['risk_flags']),
      analysisId: _asStringOrNull(json['analysis_id']),
      headline: headline.isNotEmpty ? headline : null,
      explanation: explanation.isNotEmpty ? explanation : null,
    );
  }

  bool get isUnverified => label == 'UNVERIFIED';

  int get confidencePercent => (confidence.clamp(0.0, 1.0) * 100).round();

  static VerificationResult empty() {
    return const VerificationResult(
      label: 'UNVERIFIED',
      confidence: 0.0,
      summary: '',
      rationale: <String>[],
      citations: <Map<String, dynamic>>[],
      counterEvidence: <Map<String, dynamic>>[],
      limitations: <String>[],
      recommendedNextSteps: <String>[],
      riskFlags: <String>[],
      analysisId: null,
      headline: null,
      explanation: null,
    );
  }
}

String _normalizeLabel(dynamic value) {
  final raw = _asString(value).toUpperCase().trim();
  if (raw == 'TRUE' || raw == 'FALSE' || raw == 'MIXED' || raw == 'UNVERIFIED') {
    return raw;
  }
  if (raw == 'REFUSED') {
    return 'UNVERIFIED';
  }
  return 'UNVERIFIED';
}

double _normalizeConfidence(dynamic value) {
  if (value is num) {
    final raw = value.toDouble();
    if (raw > 1.0) {
      return (raw / 100.0).clamp(0.0, 1.0);
    }
    return raw.clamp(0.0, 1.0);
  }
  if (value is String) {
    final parsed = double.tryParse(value.trim());
    if (parsed != null) {
      if (parsed > 1.0) {
        return (parsed / 100.0).clamp(0.0, 1.0);
      }
      return parsed.clamp(0.0, 1.0);
    }
  }
  return 0.0;
}

String _asString(dynamic value) {
  if (value == null) {
    return '';
  }
  return value.toString();
}

String? _asStringOrNull(dynamic value) {
  final text = _asString(value).trim();
  if (text.isEmpty) {
    return null;
  }
  return text;
}

List<String> _stringList(dynamic value) {
  if (value is! List) {
    return const <String>[];
  }
  final out = <String>[];
  for (final item in value) {
    final text = _asString(item).trim();
    if (text.isNotEmpty) {
      out.add(text);
    }
  }
  return out;
}

List<Map<String, dynamic>> _mapList(dynamic value) {
  if (value is! List) {
    return const <Map<String, dynamic>>[];
  }
  final out = <Map<String, dynamic>>[];
  for (final item in value) {
    if (item is Map<String, dynamic>) {
      out.add(item);
      continue;
    }
    if (item is Map) {
      out.add(Map<String, dynamic>.from(item));
    }
  }
  return out;
}
