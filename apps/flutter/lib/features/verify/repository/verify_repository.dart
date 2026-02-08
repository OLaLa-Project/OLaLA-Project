import '../models/verification_request.dart';
import '../models/verification_result.dart';

/// 검증 Repository 인터페이스
abstract class VerifyRepository {
  /// 검증 요청을 처리하고 결과를 반환
  ///
  /// [request]: 검증 요청 데이터
  /// [onProgress]: 진행 상황 콜백 (step: 0-2, message: 상태 메시지)
  Future<VerificationResult> verify(
    VerificationRequest request, {
    void Function(int step, String message)? onProgress,
  });
}
