class NdjsonStreamResponse {
  const NdjsonStreamResponse({
    required this.statusCode,
    required this.lines,
  });

  final int statusCode;
  final Stream<String> lines;
}
