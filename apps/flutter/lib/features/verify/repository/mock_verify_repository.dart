import '../models/verification_request.dart';
import '../models/verification_result.dart';
import '../models/evidence_card.dart';
import 'verify_repository.dart';

/// Mock 검증 Repository (개발/테스트용)
class MockVerifyRepository implements VerifyRepository {
  @override
  Future<VerificationResult> verify(
    VerificationRequest request, {
    void Function(int step, String message)? onProgress,
  }) async {
    // Step 0: 주장 분석
    onProgress?.call(0, '주장을 분석하고 있어요');
    await Future.delayed(const Duration(milliseconds: 800));

    // Step 1: 근거 수집
    onProgress?.call(1, '관련 근거를 찾고 있어요');
    await Future.delayed(const Duration(milliseconds: 1200));

    // Step 2: 최종 판단
    onProgress?.call(2, '최종 판단을 만들고 있어요');
    await Future.delayed(const Duration(milliseconds: 800));

    // Mock 데이터 반환
    return VerificationResult(
      verdict: 'true',
      confidence: 0.85,
      headline: '대체로 사실이에요',
      reason: '여러 신뢰할 수 있는 출처에서 이 주장을 뒷받침하는 근거를 찾았어요.\n'
          '아래 근거 카드에서 출처를 직접 확인해 주세요.',
      evidenceCards: [
        EvidenceCard(
          title: '관련 뉴스 기사',
          snippet: '신뢰할 수 있는 언론사에서 보도한 내용입니다...',
          url: 'https://example.com/article1',
          source: 'Example News',
          publishedAt: DateTime.now().subtract(const Duration(days: 2)).toIso8601String(),
          stance: 'support',
          score: 0.9,
        ),
        EvidenceCard(
          title: '공식 발표',
          snippet: '공식 기관에서 발표한 자료입니다...',
          url: 'https://example.com/official',
          source: 'Official Source',
          publishedAt: DateTime.now().subtract(const Duration(days: 5)).toIso8601String(),
          stance: 'support',
          score: 0.95,
        ),
        EvidenceCard(
          title: '일부 반박 의견',
          snippet: '다른 관점을 제시하는 의견도 있습니다...',
          url: 'https://example.com/counter',
          source: 'Counter View',
          publishedAt: DateTime.now().subtract(const Duration(days: 1)).toIso8601String(),
          stance: 'refute',
          score: 0.7,
        ),
      ],
    );
  }
}
