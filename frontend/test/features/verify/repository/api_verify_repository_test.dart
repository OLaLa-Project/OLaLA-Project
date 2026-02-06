import 'dart:convert';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:olala_frontend/features/verify/presentation/stream_event_adapter.dart';
import 'package:olala_frontend/features/verify/repository/api_verify_repository.dart';
import 'package:olala_frontend/shared/network/api_client.dart';

class _FakeStreamClient extends http.BaseClient {
  _FakeStreamClient(this._handler);

  final Future<http.StreamedResponse> Function(http.BaseRequest request) _handler;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) => _handler(request);
}

Future<http.StreamedResponse> _responseFromLines(
  List<String> lines, {
  int statusCode = 200,
}) async {
  final joined = '${lines.join('\n')}\n';
  final stream = Stream<List<int>>.fromIterable(<List<int>>[utf8.encode(joined)]);
  return http.StreamedResponse(
    stream,
    statusCode,
    headers: <String, String>{'content-type': 'application/x-ndjson'},
  );
}

void main() {
  test('requests v2 endpoint and parses heartbeat events', () async {
    String? requestedPath;
    final client = _FakeStreamClient((request) {
      requestedPath = request.url.path;
      return _responseFromLines(<String>[
        '{"event":"stream_open","trace_id":"t1","ts":"2026-02-06T10:00:00Z"}',
        '{"event":"heartbeat","trace_id":"t1","current_stage":"stage08_aggregate","idle_ms":2100,"ts":"2026-02-06T10:00:02Z"}',
        '{"event":"complete","data":{"label":"TRUE","confidence":0.9}}',
      ]);
    });

    final repository = ApiVerifyRepository(client: ApiClient(client: client));
    final events = await repository.verifyTruthStream(input: 'x', inputType: 'text').toList();

    expect(requestedPath, '/api/truth/check/stream-v2');
    expect(events.length, 3);
    expect(events[0].type, StreamEventType.streamOpen);
    expect(events[1].type, StreamEventType.heartbeat);
    expect(events[1].currentStage, 'stage08_aggregate');
    expect(events[2].type, StreamEventType.complete);
  });

  test('emits terminal error when stream ends without complete', () async {
    final client = _FakeStreamClient((_) {
      return _responseFromLines(<String>[
        '{"event":"stage_complete","stage":"stage01_normalize","data":{"claim_text":"x"}}',
      ]);
    });

    final repository = ApiVerifyRepository(client: ApiClient(client: client));
    final events = await repository.verifyTruthStream(input: 'x', inputType: 'text').toList();

    expect(events.length, 2);
    expect(events.first.type, StreamEventType.stageComplete);
    expect(events.last.type, StreamEventType.error);
    expect(events.last.data['message'], contains('complete'));
  });

  test('skips malformed lines and succeeds when complete exists', () async {
    final client = _FakeStreamClient((_) {
      return _responseFromLines(<String>[
        '{"event":"stage_complete","stage":"stage02_querygen","data":{"search_queries":[]}}',
        '{"event":"bad_json"',
        '{"event":"complete","data":{"label":"TRUE","confidence":0.9}}',
      ]);
    });

    final repository = ApiVerifyRepository(client: ApiClient(client: client));
    final events = await repository.verifyTruthStream(input: 'x', inputType: 'text').toList();

    expect(events.length, 2);
    expect(events.first.type, StreamEventType.stageComplete);
    expect(events.last.type, StreamEventType.complete);
    expect(events.last.data['label'], 'TRUE');
  });
}
