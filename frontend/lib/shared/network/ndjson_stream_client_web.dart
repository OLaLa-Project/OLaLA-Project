import 'dart:async';

import 'dart:html' as html;
import 'package:http/http.dart' as http;

import 'ndjson_stream_types.dart';

Future<NdjsonStreamResponse> postNdjsonStream({
  required http.Client client,
  required Uri url,
  Map<String, String>? headers,
  String? body,
}) {
  final completer = Completer<NdjsonStreamResponse>();
  final controller = StreamController<String>();
  final request = html.HttpRequest();
  final buffer = StringBuffer();
  var emittedLength = 0;
  var closed = false;

  void closeController() {
    if (!closed) {
      closed = true;
      controller.close();
    }
  }

  void emitNewLines() {
    final text = request.responseText ?? '';
    if (text.length <= emittedLength) {
      return;
    }
    final chunk = text.substring(emittedLength);
    emittedLength = text.length;
    buffer.write(chunk);

    final data = buffer.toString();
    final segments = data.split('\n');
    if (segments.isEmpty) {
      return;
    }

    for (var i = 0; i < segments.length - 1; i++) {
      controller.add(segments[i]);
    }

    final remainder = segments.last;
    buffer
      ..clear()
      ..write(remainder);
  }

  request.onReadyStateChange.listen((_) {
    final state = request.readyState;
    if (state >= html.HttpRequest.HEADERS_RECEIVED && !completer.isCompleted) {
      completer.complete(
        NdjsonStreamResponse(
          statusCode: request.status ?? 0,
          lines: controller.stream,
        ),
      );
    }

    if (state >= html.HttpRequest.LOADING) {
      emitNewLines();
    }

    if (state == html.HttpRequest.DONE) {
      emitNewLines();
      final tail = buffer.toString();
      if (tail.isNotEmpty) {
        controller.add(tail);
      }
      closeController();
    }
  });

  request.onError.listen((_) {
    if (!completer.isCompleted) {
      completer.complete(
        NdjsonStreamResponse(
          statusCode: request.status ?? 0,
          lines: controller.stream,
        ),
      );
    }
    controller.addError(Exception('Web stream request failed'));
    closeController();
  });

  request.onAbort.listen((_) {
    if (!completer.isCompleted) {
      completer.complete(
        NdjsonStreamResponse(
          statusCode: request.status ?? 0,
          lines: controller.stream,
        ),
      );
    }
    controller.addError(Exception('Web stream request aborted'));
    closeController();
  });

  request.open('POST', url.toString(), async: true);
  if (headers != null) {
    headers.forEach(request.setRequestHeader);
  }
  request.send(body);
  return completer.future;
}
