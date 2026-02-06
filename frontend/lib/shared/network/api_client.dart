import 'package:http/http.dart' as http;
import 'package:flutter/foundation.dart';

class ApiClient {
  static const String baseUrl = String.fromEnvironment('API_URL', defaultValue: 'http://127.0.0.1:8080');

  final http.Client client;

  ApiClient({http.Client? client}) : client = client ?? http.Client();

  Future<http.Response> post(String endpoint, {Map<String, String>? headers, Object? body}) async {
    final url = Uri.parse('$baseUrl$endpoint');
    return await client.post(
      url,
      headers: headers,
      body: body,
    );
  }

  /// Streaming POST request (returns response stream)
  Future<http.StreamedResponse> postStream(
    String endpoint, {
    Map<String, String>? headers,
    Object? body,
  }) async {
    debugPrint('[API] 📤 Creating request: $baseUrl$endpoint');
    final url = Uri.parse('$baseUrl$endpoint');
    final request = http.Request('POST', url);
    
    if (headers != null) {
      request.headers.addAll(headers);
      debugPrint('[API] 📋 Headers: $headers');
    }
    
    if (body != null) {
      request.body = body as String;
      debugPrint('[API] 📦 Body length: ${(body as String).length} bytes');
    }
    
    debugPrint('[API] 🚀 Sending request...');
    final response = await client.send(request);
    debugPrint('[API] ✅ Response received: ${response.statusCode}');
    return response;
  }
}
