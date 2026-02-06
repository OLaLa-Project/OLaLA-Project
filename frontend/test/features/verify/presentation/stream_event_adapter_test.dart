import 'package:flutter_test/flutter_test.dart';
import 'package:olala_frontend/features/verify/presentation/stream_event_adapter.dart';

void main() {
  test('stream_open event parses trace id and timestamp', () {
    final event = normalizeStreamEvent(<String, dynamic>{
      'event': 'stream_open',
      'trace_id': 'trace-123',
      'ts': '2026-02-06T10:00:00Z',
    });

    expect(event.type, StreamEventType.streamOpen);
    expect(event.traceId, 'trace-123');
    expect(event.serverTimestamp, DateTime.parse('2026-02-06T10:00:00Z'));
  });

  test('heartbeat event parses current stage and idle ms', () {
    final event = normalizeStreamEvent(<String, dynamic>{
      'event': 'heartbeat',
      'current_stage': 'stage07_verify_skeptic',
      'idle_ms': 2500,
      'trace_id': 'trace-123',
    });

    expect(event.type, StreamEventType.heartbeat);
    expect(event.currentStage, 'stage07_verify_skeptic');
    expect(event.uiStep, 3);
    expect(event.idleMs, 2500);
  });

  test('stage_complete event falls back ui_step from stage name', () {
    final event = normalizeStreamEvent(<String, dynamic>{
      'event': 'stage_complete',
      'stage': 'stage03_web',
      'data': <String, dynamic>{},
    });

    expect(event.type, StreamEventType.stageComplete);
    expect(event.uiStep, 2);
    expect(event.uiStepTitle, '관련 근거 수집');
  });

  test('error event keeps payload and stage from data when missing', () {
    final event = normalizeStreamEvent(<String, dynamic>{
      'event': 'error',
      'data': <String, dynamic>{
        'stage': 'stage07_verify_skeptic',
        'message': 'failed',
      },
    });

    expect(event.type, StreamEventType.error);
    expect(event.stage, 'stage07_verify_skeptic');
    expect(event.data['message'], 'failed');
  });

  test('unknown event is classified safely', () {
    final event = normalizeStreamEvent(<String, dynamic>{
      'event': 'something_new',
      'data': <String, dynamic>{'x': 1},
    });

    expect(event.type, StreamEventType.unknown);
    expect(event.event, 'something_new');
    expect(event.data['x'], 1);
  });
}
