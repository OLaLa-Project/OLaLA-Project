enum StreamEventType {
  streamOpen,
  heartbeat,
  stepStarted,
  stepCompleted,
  stageComplete,
  complete,
  error,
  unknown,
}

class StreamEvent {
  const StreamEvent({
    required this.type,
    required this.event,
    required this.receivedAt,
    this.traceId,
    this.serverTimestamp,
    this.stage,
    this.currentStage,
    this.idleMs,
    this.uiStep,
    this.uiStepTitle,
    this.data = const <String, dynamic>{},
  });

  final StreamEventType type;
  final String event;
  final String? traceId;
  final DateTime? serverTimestamp;
  final String? stage;
  final String? currentStage;
  final int? idleMs;
  final int? uiStep;
  final String? uiStepTitle;
  final Map<String, dynamic> data;
  final DateTime receivedAt;

  static StreamEvent error({
    required String message,
    String? stage,
    Map<String, dynamic> data = const <String, dynamic>{},
    DateTime? receivedAt,
  }) {
    final payload = <String, dynamic>{...data};
    payload.putIfAbsent('message', () => message);
    return StreamEvent(
      type: StreamEventType.error,
      event: 'error',
      stage: stage,
      currentStage: stage,
      data: payload,
      receivedAt: receivedAt ?? DateTime.now(),
    );
  }
}

StreamEvent normalizeStreamEvent(
  Map<String, dynamic> rawEvent, {
  DateTime? receivedAt,
}) {
  final seenAt = receivedAt ?? DateTime.now();
  final rawType = (rawEvent['event'] as String?)?.trim().toLowerCase() ?? 'unknown';
  final stage = (rawEvent['stage'] as String?)?.trim();
  final data = _coerceMap(rawEvent['data']);
  final traceId = _toString(rawEvent['trace_id']) ?? _toString(data['trace_id']);
  final serverTimestamp = _parseDateTime(
    _toString(rawEvent['ts']) ?? _toString(data['ts']),
  );
  final currentStage =
      _toString(rawEvent['current_stage']) ??
      stage ??
      _toString(data['current_stage']);
  final idleMs = _toInt(rawEvent['idle_ms']) ?? _toInt(data['idle_ms']);
  final explicitUiStep = _toInt(rawEvent['ui_step']) ?? _toInt(data['ui_step']);
  final fallbackUiStep = explicitUiStep ?? _fallbackUiStepForStage(stage ?? currentStage);
  final explicitUiStepTitle = _toString(rawEvent['ui_step_title']) ?? _toString(data['ui_step_title']);
  final fallbackUiStepTitle = explicitUiStepTitle ?? _defaultUiStepTitle(fallbackUiStep);

  switch (rawType) {
    case 'stream_open':
      return StreamEvent(
        type: StreamEventType.streamOpen,
        event: 'stream_open',
        traceId: traceId,
        serverTimestamp: serverTimestamp,
        stage: stage ?? currentStage,
        currentStage: currentStage,
        idleMs: idleMs,
        uiStep: fallbackUiStep,
        uiStepTitle: fallbackUiStepTitle,
        data: data,
        receivedAt: seenAt,
      );
    case 'heartbeat':
      return StreamEvent(
        type: StreamEventType.heartbeat,
        event: 'heartbeat',
        traceId: traceId,
        serverTimestamp: serverTimestamp,
        stage: stage ?? currentStage,
        currentStage: currentStage,
        idleMs: idleMs,
        uiStep: fallbackUiStep,
        uiStepTitle: fallbackUiStepTitle,
        data: data,
        receivedAt: seenAt,
      );
    case 'step_started':
      return StreamEvent(
        type: StreamEventType.stepStarted,
        event: 'step_started',
        traceId: traceId,
        serverTimestamp: serverTimestamp,
        stage: stage,
        currentStage: currentStage,
        idleMs: idleMs,
        uiStep: fallbackUiStep,
        uiStepTitle: fallbackUiStepTitle,
        data: data,
        receivedAt: seenAt,
      );
    case 'step_completed':
      return StreamEvent(
        type: StreamEventType.stepCompleted,
        event: 'step_completed',
        traceId: traceId,
        serverTimestamp: serverTimestamp,
        stage: stage,
        currentStage: currentStage,
        idleMs: idleMs,
        uiStep: fallbackUiStep,
        uiStepTitle: fallbackUiStepTitle,
        data: data,
        receivedAt: seenAt,
      );
    case 'stage_complete':
      return StreamEvent(
        type: StreamEventType.stageComplete,
        event: 'stage_complete',
        traceId: traceId,
        serverTimestamp: serverTimestamp,
        stage: stage,
        currentStage: currentStage,
        idleMs: idleMs,
        uiStep: fallbackUiStep,
        uiStepTitle: fallbackUiStepTitle,
        data: data,
        receivedAt: seenAt,
      );
    case 'complete':
      return StreamEvent(
        type: StreamEventType.complete,
        event: 'complete',
        traceId: traceId,
        serverTimestamp: serverTimestamp,
        stage: stage,
        currentStage: currentStage,
        idleMs: idleMs,
        uiStep: fallbackUiStep,
        uiStepTitle: fallbackUiStepTitle,
        data: data,
        receivedAt: seenAt,
      );
    case 'error':
      return StreamEvent(
        type: StreamEventType.error,
        event: 'error',
        traceId: traceId,
        serverTimestamp: serverTimestamp,
        stage: stage ?? _toString(data['stage']) ?? currentStage,
        currentStage: currentStage,
        idleMs: idleMs,
        uiStep: fallbackUiStep,
        uiStepTitle: fallbackUiStepTitle,
        data: data,
        receivedAt: seenAt,
      );
    default:
      return StreamEvent(
        type: StreamEventType.unknown,
        event: rawType,
        traceId: traceId,
        serverTimestamp: serverTimestamp,
        stage: stage,
        currentStage: currentStage,
        idleMs: idleMs,
        uiStep: fallbackUiStep,
        uiStepTitle: fallbackUiStepTitle,
        data: data,
        receivedAt: seenAt,
      );
  }
}

DateTime? _parseDateTime(String? value) {
  if (value == null || value.isEmpty) {
    return null;
  }
  return DateTime.tryParse(value);
}

Map<String, dynamic> _coerceMap(dynamic value) {
  if (value is Map<String, dynamic>) {
    return value;
  }
  if (value is Map) {
    return Map<String, dynamic>.from(value);
  }
  return const <String, dynamic>{};
}

int? _toInt(dynamic value) {
  if (value is int) {
    return value;
  }
  if (value is num) {
    return value.toInt();
  }
  if (value is String) {
    return int.tryParse(value);
  }
  return null;
}

String? _toString(dynamic value) {
  if (value == null) {
    return null;
  }
  if (value is String) {
    final trimmed = value.trim();
    return trimmed.isEmpty ? null : trimmed;
  }
  return value.toString();
}

int? _fallbackUiStepForStage(String? stage) {
  if (stage == null || stage.isEmpty) {
    return null;
  }
  if (stage.startsWith('stage01') || stage.startsWith('stage02') || stage == 'adapter_queries') {
    return 1;
  }
  if (stage.startsWith('stage03') || stage.startsWith('stage04') || stage.startsWith('stage05')) {
    return 2;
  }
  if (stage.startsWith('stage06') || stage.startsWith('stage07') || stage.startsWith('stage08') || stage.startsWith('stage09')) {
    return 3;
  }
  return null;
}

String? _defaultUiStepTitle(int? uiStep) {
  switch (uiStep) {
    case 1:
      return '주장/콘텐츠 추출';
    case 2:
      return '관련 근거 수집';
    case 3:
      return '근거 기반 판단 제공';
    default:
      return null;
  }
}
