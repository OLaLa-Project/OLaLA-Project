import 'dart:convert';

import 'package:http/http.dart' as http;

import 'ndjson_stream_types.dart';

Future<NdjsonStreamResponse> postNdjsonStream({
  required http.Client client,
  required Uri url,
  Map<String, String>? headers,
  String? body,
}) async {
  final request = http.Request('POST', url);
  if (headers != null) {
    request.headers.addAll(headers);
  }
  if (body != null) {
    request.body = body;
  }

  final response = await client.send(request);
  final lines = response.stream
      .transform(utf8.decoder)
      .transform(const LineSplitter());
  return NdjsonStreamResponse(
    statusCode: response.statusCode,
    lines: lines,
  );
}
