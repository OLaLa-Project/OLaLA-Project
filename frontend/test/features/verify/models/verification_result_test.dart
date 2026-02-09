import 'package:flutter_test/flutter_test.dart';
import 'package:olala_frontend/features/verify/models/verification_result.dart';

void main() {
  test('parses gateway complete payload safely', () {
    final result = VerificationResult.fromJson(<String, dynamic>{
      'analysis_id': 'trace-1',
      'label': 'FALSE',
      'confidence': 0.64,
      'summary': '이 주장은 64% 확률로 거짓입니다',
      'rationale': <String>['근거1', '근거2'],
      'citations': <Map<String, dynamic>>[
        <String, dynamic>{
          'source_type': 'NEWS',
          'title': '기사',
          'url': 'https://example.com',
          'quote': '인용',
        },
      ],
      'limitations': <String>['추가 확인 필요'],
      'recommended_next_steps': <String>['공식 자료 확인'],
      'risk_flags': <String>['LOW_EVIDENCE'],
    });

    expect(result.analysisId, 'trace-1');
    expect(result.label, 'FALSE');
    expect(result.confidence, closeTo(0.64, 0.0001));
    expect(result.confidencePercent, 64);
    expect(result.citations.length, 1);
    expect(result.riskFlags, contains('LOW_EVIDENCE'));
  });

  test('normalizes percent confidence values', () {
    final result = VerificationResult.fromJson(<String, dynamic>{
      'label': 'TRUE',
      'confidence': 85,
      'summary': '요약',
    });

    expect(result.label, 'TRUE');
    expect(result.confidence, closeTo(0.85, 0.0001));
    expect(result.confidencePercent, 85);
  });

  test('maps unknown/refused label to UNVERIFIED', () {
    final result = VerificationResult.fromJson(<String, dynamic>{
      'label': 'REFUSED',
      'confidence': 0.2,
      'summary': '요약',
    });

    expect(result.label, 'UNVERIFIED');
    expect(result.isUnverified, isTrue);
  });
}
