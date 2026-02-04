/// 팩트체크 요청 타입
enum InputType {
  url,
  text,
  image;

  String get value => name;
}

/// 팩트체크 판정 라벨
enum TruthLabel {
  TRUE,
  FALSE,
  MIXED,
  UNVERIFIED,
  REFUSED;

  String get displayName {
    switch (this) {
      case TruthLabel.TRUE:
        return '사실';
      case TruthLabel.FALSE:
        return '거짓';
      case TruthLabel.MIXED:
        return '부분 사실';
      case TruthLabel.UNVERIFIED:
        return '검증 불가';
      case TruthLabel.REFUSED:
        return '판정 거부';
    }
  }
}

/// 인용 출처 타입
enum SourceType {
  KB_DOC,
  WEB_URL,
  NEWS,
  WIKIPEDIA;

  String get value => name;
}

/// 팩트체크 요청 모델
class TruthCheckRequest {
  final InputType inputType;
  final String inputPayload;
  final String? userRequest;
  final String? asOf;
  final String language;
  final bool includeFullOutputs;

  TruthCheckRequest({
    required this.inputType,
    required this.inputPayload,
    this.userRequest,
    this.asOf,
    this.language = 'ko',
    this.includeFullOutputs = false,
  });

  Map<String, dynamic> toJson() {
    return {
      'input_type': inputType.value,
      'input_payload': inputPayload,
      if (userRequest != null) 'user_request': userRequest,
      if (asOf != null) 'as_of': asOf,
      'language': language,
      'include_full_outputs': includeFullOutputs,
    };
  }
}

/// 인용/출처 정보
class Citation {
  final SourceType sourceType;
  final String title;
  final String? url;
  final String? quote;
  final double? relevance;
  final String? evidId;

  Citation({
    required this.sourceType,
    required this.title,
    this.url,
    this.quote,
    this.relevance,
    this.evidId,
  });

  factory Citation.fromJson(Map<String, dynamic> json) {
    return Citation(
      sourceType: SourceType.values.firstWhere(
        (e) => e.value == json['source_type'],
        orElse: () => SourceType.WEB_URL,
      ),
      title: json['title'] as String,
      url: json['url'] as String?,
      quote: json['quote'] as String?,
      relevance: (json['relevance'] as num?)?.toDouble(),
      evidId: json['evid_id'] as String?,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'source_type': sourceType.value,
      'title': title,
      if (url != null) 'url': url,
      if (quote != null) 'quote': quote,
      if (relevance != null) 'relevance': relevance,
      if (evidId != null) 'evid_id': evidId,
    };
  }
}

/// 모델 정보
class ModelInfo {
  final String provider;
  final String model;
  final String version;

  ModelInfo({
    required this.provider,
    required this.model,
    required this.version,
  });

  factory ModelInfo.fromJson(Map<String, dynamic> json) {
    return ModelInfo(
      provider: json['provider'] as String,
      model: json['model'] as String,
      version: json['version'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'provider': provider,
      'model': model,
      'version': version,
    };
  }
}

/// 팩트체크 응답 모델
class TruthCheckResponse {
  final String analysisId;
  final TruthLabel label;
  final double confidence;
  final String summary;
  final List<String> rationale;
  final List<Citation> citations;
  final List<Map<String, dynamic>> counterEvidence;
  final List<String> limitations;
  final List<String> recommendedNextSteps;
  final List<String> riskFlags;
  final List<Map<String, dynamic>> stageLogs;
  final Map<String, dynamic> stageOutputs;
  final Map<String, dynamic> stageFullOutputs;
  final ModelInfo modelInfo;
  final int latencyMs;
  final double costUsd;
  final String createdAt;

  TruthCheckResponse({
    required this.analysisId,
    required this.label,
    required this.confidence,
    required this.summary,
    required this.rationale,
    required this.citations,
    required this.counterEvidence,
    required this.limitations,
    required this.recommendedNextSteps,
    required this.riskFlags,
    required this.stageLogs,
    required this.stageOutputs,
    required this.stageFullOutputs,
    required this.modelInfo,
    required this.latencyMs,
    required this.costUsd,
    required this.createdAt,
  });

  factory TruthCheckResponse.fromJson(Map<String, dynamic> json) {
    return TruthCheckResponse(
      analysisId: json['analysis_id'] as String,
      label: TruthLabel.values.firstWhere(
        (e) => e.name == json['label'],
        orElse: () => TruthLabel.UNVERIFIED,
      ),
      confidence: (json['confidence'] as num).toDouble(),
      summary: json['summary'] as String,
      rationale: (json['rationale'] as List?)?.cast<String>() ?? [],
      citations: (json['citations'] as List?)
              ?.map((e) => Citation.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      counterEvidence: (json['counter_evidence'] as List?)
              ?.cast<Map<String, dynamic>>() ??
          [],
      limitations: (json['limitations'] as List?)?.cast<String>() ?? [],
      recommendedNextSteps:
          (json['recommended_next_steps'] as List?)?.cast<String>() ?? [],
      riskFlags: (json['risk_flags'] as List?)?.cast<String>() ?? [],
      stageLogs: (json['stage_logs'] as List?)?.cast<Map<String, dynamic>>() ?? [],
      stageOutputs: json['stage_outputs'] as Map<String, dynamic>? ?? {},
      stageFullOutputs: json['stage_full_outputs'] as Map<String, dynamic>? ?? {},
      modelInfo: ModelInfo.fromJson(json['model_info'] as Map<String, dynamic>),
      latencyMs: json['latency_ms'] as int,
      costUsd: (json['cost_usd'] as num).toDouble(),
      createdAt: json['created_at'] as String,
    );
  }

  /// 신뢰도 백분율
  String get confidencePercent => '${(confidence * 100).toStringAsFixed(1)}%';

  /// 판정 결과가 신뢰할 수 있는지 (70% 이상)
  bool get isReliable => confidence >= 0.7;
}
