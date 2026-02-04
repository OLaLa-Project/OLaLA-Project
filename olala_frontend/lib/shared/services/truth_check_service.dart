import 'dart:async';
import '../../data/provider/api_client.dart';
// import '../network/api_result.dart'; // Removing dependency on old result wrapper for stream simplicity, or adapting.

/// 팩트체크 API 서비스
class TruthCheckService {
  final OLaLaApiClient _client = OLaLaApiClient();

  /// 팩트체크 요청 (스트리밍)
  Stream<Map<String, dynamic>> checkTruthStream(TruthCheckRequest request) {
    return _client.checkTruthStream(request);
  }

  /// 팩트체크 요청 (Legacy/Simple) - keeping for compatibility if needed, but implementation redirects to new client logic if I added it.
  /// For now, I only implemented streaming in OLaLaApiClient.
}
