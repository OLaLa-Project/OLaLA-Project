class VerificationRequest {
  final String input;
  final DateTime timestamp;

  VerificationRequest({
    required this.input,
    required this.timestamp,
  });

  factory VerificationRequest.fromInput(String input) {
    return VerificationRequest(
      input: input,
      timestamp: DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'input': input,
      'timestamp': timestamp.toIso8601String(),
    };
  }
}
