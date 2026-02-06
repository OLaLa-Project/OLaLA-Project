import 'dart:convert';
import 'dart:async';
import 'package:flutter/foundation.dart';
import '../../../shared/network/api_client.dart';

class ApiVerifyRepository {
  final ApiClient _client;

  ApiVerifyRepository({ApiClient? client}) : _client = client ?? ApiClient();

  Future<Map<String, dynamic>> verifyTruth({
    required String input,
    required String inputType,
  }) async {
    try {
      final response = await _client.post(
        '/api/truth/check',
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
  Stream<Map<String, dynamic>> verifyTruthStream({
    required String input,
    required String inputType,
  }) async* {
    try {
      debugPrint('[REPO] 📡 Sending stream request...');
      final response = await _client.postStream(
        '/api/truth/check/stream',
        headers: {'Content-Type': 'application/json'},
        body: jsonEncode({
          'input_payload': input,
          'input_type': inputType,
        }),
      );

      if (response.statusCode != 200) {
        debugPrint('[REPO] ❌ Stream failed: ${response.statusCode}');
        throw Exception('Failed to start stream: ${response.statusCode}');
      }

      debugPrint('[REPO] ✅ Stream connected, parsing NDJSON...');
      // Parse NDJSON stream (newline-delimited JSON)
      final stream = response.stream.transform(utf8.decoder).transform(const LineSplitter());

      int lineCount = 0;
      await for (final line in stream) {
        lineCount++;
        if (line.trim().isEmpty) {
          debugPrint('[REPO] ⚠️  Empty line #$lineCount, skipping');
          continue;
        }
        
        debugPrint('[REPO] 📥 Line #$lineCount: ${line.substring(0, line.length > 100 ? 100 : line.length)}...');
        
        try {
          final event = jsonDecode(line) as Map<String, dynamic>;
          debugPrint('[REPO] ✅ Parsed event: ${event['event']}');
          yield event;
        } catch (e) {
          debugPrint('[REPO] ⚠️  JSON parse error on line #$lineCount: $e');
          // Skip malformed JSON lines
          continue;
        }
      }
      debugPrint('[REPO] 🏁 Stream ended after $lineCount lines');
    } catch (e) {
      debugPrint('[REPO] 💥 Exception: $e');
      yield {
        'event': 'error',
        'data': {
          'message': e.toString(),
        }
      };
    }
  }
}
