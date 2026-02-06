import 'package:http/http.dart' as http;

import 'ndjson_stream_types.dart';
import 'ndjson_stream_client_io.dart'
    if (dart.library.html) 'ndjson_stream_client_web.dart' as impl;

Future<NdjsonStreamResponse> postNdjsonStream({
  required http.Client client,
  required Uri url,
  Map<String, String>? headers,
  String? body,
}) {
  return impl.postNdjsonStream(
    client: client,
    url: url,
    headers: headers,
    body: body,
  );
}
