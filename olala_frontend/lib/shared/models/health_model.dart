/// 헬스체크 응답 모델
class HealthResponse {
  final String status;

  HealthResponse({required this.status});

  factory HealthResponse.fromJson(Map<String, dynamic> json) {
    return HealthResponse(
      status: json['status'] as String? ?? 'unknown',
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'status': status,
    };
  }

  bool get isHealthy => status == 'healthy';
}
