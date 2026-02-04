import '../models/health_model.dart';
import '../network/api_client.dart';
import '../network/api_result.dart';

/// 헬스체크 API 서비스
class HealthService {
  final ApiClient _client;

  HealthService({ApiClient? client}) : _client = client ?? ApiClient.instance;

  /// 서버 상태 확인
  ///
  /// Returns: [ApiResult<HealthResponse>]
  Future<ApiResult<HealthResponse>> checkHealth() async {
    return await _client.get<HealthResponse>(
      '/health',
      parser: (data) => HealthResponse.fromJson(data as Map<String, dynamic>),
    );
  }
}
