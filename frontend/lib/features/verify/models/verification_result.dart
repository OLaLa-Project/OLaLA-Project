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
    this.verdictKorean,
    this.confidencePercentRaw,
    this.evaluation,
    this.evidenceSummary = const <Map<String, dynamic>>[],
    this.userResult,
    this.schemaVersion,
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
  final String? verdictKorean;
  final int? confidencePercentRaw;
  final Map<String, dynamic>? evaluation;
  final List<Map<String, dynamic>> evidenceSummary;
  final Map<String, dynamic>? userResult;
  final String? schemaVersion;

  factory VerificationResult.fromJson(Map<String, dynamic> json) {
    final confidenceRaw = json['confidence'];
    final confidence = _normalizeConfidence(confidenceRaw);
    final userResult = _asMap(json['user_result']);
    final userVerdict = _asMap(userResult?['verdict']);

    final summary = _asString(json['summary']);
    final headline = _asString(
      json['headline'] ?? userResult?['headline'],
    );
    final explanation = _asString(
      json['explanation'] ?? userResult?['explanation'],
    );
    final confidencePercentRaw =
        _asInt(json['confidence_percent']) ?? _asInt(userVerdict?['confidence_percent']);

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
      verdictKorean:
          _asStringOrNull(json['verdict_korean']) ?? _asStringOrNull(userVerdict?['korean']),
      confidencePercentRaw: confidencePercentRaw,
      evaluation: _asMap(json['evaluation']),
      evidenceSummary: _mapList(json['evidence_summary']),
      userResult: userResult,
      schemaVersion: _asStringOrNull(json['schema_version']),
    );
  }

  bool get isUnverified => label == 'UNVERIFIED';

  int get confidencePercent {
    if (confidencePercentRaw != null) {
      return confidencePercentRaw!.clamp(0, 100);
    }
    return (confidence.clamp(0.0, 1.0) * 100).round();
  }

  String? get evaluationReason {
    final eval = evaluation;
    if (eval == null) {
      return null;
    }
    final reason = _asStringOrNull(eval['reason']);
    if (reason != null) {
      return reason;
    }
    final caution = _asStringOrNull(eval['caution']);
    if (caution != null) {
      return caution;
    }
    return null;
  }

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
      verdictKorean: null,
      confidencePercentRaw: null,
      evaluation: null,
      evidenceSummary: <Map<String, dynamic>>[],
      userResult: null,
      schemaVersion: null,
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

Map<String, dynamic>? _asMap(dynamic value) {
  if (value is Map<String, dynamic>) {
    return value;
  }
  if (value is Map) {
    return Map<String, dynamic>.from(value);
  }
  return null;
}

int? _asInt(dynamic value) {
  if (value is int) {
    return value;
  }
  if (value is num) {
    return value.toInt();
  }
  if (value is String) {
    return int.tryParse(value.trim());
  }
  return null;
}
