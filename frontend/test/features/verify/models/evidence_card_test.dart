import 'package:flutter_test/flutter_test.dart';
import 'package:olala_frontend/features/verify/models/evidence_card.dart';

void main() {
  test('parses backend citation fields including source_type', () {
    final card = EvidenceCard.fromJson(<String, dynamic>{
      'source_type': 'NEWS',
      'title': '기사 제목',
      'url': 'https://news.example.com/article/1',
      'quote': '검증 인용문',
      'relevance': 0.82,
    });

    expect(card.title, '기사 제목');
    expect(card.source, 'NEWS');
    expect(card.snippet, '검증 인용문');
    expect(card.url, 'https://news.example.com/article/1');
    expect(card.score, closeTo(0.82, 0.0001));
  });

  test('falls back to url host when source is missing', () {
    final card = EvidenceCard.fromJson(<String, dynamic>{
      'title': '제목',
      'url': 'https://m.entertain.naver.com/article/477/0000431266',
      'quote': '본문',
    });

    expect(card.source, 'm.entertain.naver.com');
  });
}
