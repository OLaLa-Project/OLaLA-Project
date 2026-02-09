import 'dart:convert';
import 'dart:async';
import 'package:flutter/foundation.dart';
import '../../../shared/network/api_client.dart';
import '../../../shared/network/ndjson_stream_client.dart';
import '../presentation/stream_event_adapter.dart';
import 'verify_endpoints.dart';

class ApiVerifyRepository {
  final ApiClient _client;

  ApiVerifyRepository({ApiClient? client}) : _client = client ?? ApiClient();

  Future<Map<String, dynamic>> verifyTruth({
    required String input,
    required String inputType,
  }) async {
    try {
      final response = await _client.post(
        VerifyEndpoints.truthCheck,
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'input_payload': input,
          'input_type': inputType,
        }),
      );

      if (response.statusCode == 200) {
        return jsonDecode(utf8.decode(response.bodyBytes));
      } else {
        throw Exception('Failed to verify: ${response.statusCode}');
      }
    } catch (e) {
      throw Exception('Error: $e');
    }
  }

  /// Stream-based verification with stage-by-stage progress updates
  Stream<StreamEvent> verifyTruthStream({
    required String input,
    required String inputType,
  }) async* {
    try {
      debugPrint('[REPO] 📡 Sending stream request...');
      final requestBody = jsonEncode({
        'input_payload': input,
        'input_type': inputType,
      });
      final response = await postNdjsonStream(
        client: _client.client,
        url: Uri.parse('${ApiClient.baseUrl}${VerifyEndpoints.truthCheckStreamV2}'),
        headers: {'Content-Type': 'application/json'},
        body: requestBody,
      );

      if (response.statusCode != 200) {
        debugPrint('[REPO] ❌ Stream failed: ${response.statusCode}');
        throw Exception('Failed to start stream: ${response.statusCode}');
      }

      debugPrint('[REPO] ✅ Stream connected, parsing NDJSON...');
      final stream = response.lines;

      int lineCount = 0;
      int malformedLineCount = 0;
      DateTime? lastLineReceivedAt;
      bool sawCompleteEvent = false;

      await for (final line in stream) {
        lineCount++;
        if (line.trim().isEmpty) {
          debugPrint('[REPO] ⚠️  Empty line #$lineCount, skipping');
          continue;
        }

        debugPrint('[REPO] 📥 Line #$lineCount: ${line.substring(0, line.length > 100 ? 100 : line.length)}...');
        final receivedAt = DateTime.now();

        try {
          final decoded = jsonDecode(line);
          if (decoded is! Map) {
            malformedLineCount++;
            debugPrint('[REPO] ⚠️  Non-map JSON on line #$lineCount, skipping');
            continue;
          }
          final rawEvent = Map<String, dynamic>.from(decoded);
          final event = normalizeStreamEvent(rawEvent, receivedAt: receivedAt);
          lastLineReceivedAt = receivedAt;
          debugPrint('[REPO] ✅ Parsed event: ${event.event}');
          if (event.type == StreamEventType.complete) {
            sawCompleteEvent = true;
          }
          yield event;
        } catch (e) {
          malformedLineCount++;
          debugPrint('[REPO] ⚠️  JSON parse error on line #$lineCount: $e');
          // Skip malformed JSON lines
          continue;
        }
      }
      debugPrint(
        '[REPO] 🏁 Stream ended after $lineCount lines (malformed=$malformedLineCount)',
      );
      if (!sawCompleteEvent) {
        yield StreamEvent.error(
          message: 'Stream ended before complete event',
          data: <String, dynamic>{
            'line_count': lineCount,
            'malformed_line_count': malformedLineCount,
            if (lastLineReceivedAt != null)
              'last_line_received_at': lastLineReceivedAt.toIso8601String(),
          },
          receivedAt: DateTime.now(),
        );
      }
    } catch (e) {
      debugPrint('[REPO] 💥 Exception: $e');
      yield StreamEvent.error(
        message: e.toString(),
        receivedAt: DateTime.now(),
      );
    }
  }
}
