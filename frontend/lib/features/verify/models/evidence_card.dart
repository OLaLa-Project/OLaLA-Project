// lib/features/verify/models/evidence_card.dart

class EvidenceCard {
  final String? title;
  final String? source;
  final String? snippet;
  final String? url;

  // (선택) 확장용
  final double? score;
  final String? publishedAt;
  final String? stance; // support/refute/neutral 등

  const EvidenceCard({
    this.title,
    this.source,
    this.snippet,
    this.url,
    this.score,
    this.publishedAt,
    this.stance,
  });

  factory EvidenceCard.fromJson(Map<String, dynamic> json) {
    double? toDouble(dynamic v) {
      if (v == null) return null;
      if (v is num) return v.toDouble();
      return double.tryParse(v.toString());
    }

    String? toStr(dynamic v) => v?.toString();

    String? sourceFromUrl(dynamic v) {
      final raw = toStr(v);
      if (raw == null || raw.isEmpty) return null;
      final uri = Uri.tryParse(raw);
      final host = uri?.host ?? '';
      if (host.isEmpty) return null;
      return host;
    }

    return EvidenceCard(
      title: toStr(json['title'] ?? json['headline'] ?? json['source_title']),
      source: toStr(
        json['source'] ??
            json['publisher'] ??
            json['domain'] ??
            json['source_type'] ??
            sourceFromUrl(json['url'] ?? json['link']),
      ),
      snippet: toStr(
        json['snippet'] ?? json['summary'] ?? json['quote'] ?? json['point'],
      ),
      url: toStr(json['url'] ?? json['link'] ?? json['source_url']),
      score: toDouble(
        json['score'] ??
            json['relevance'] ??
            json['confidence'] ??
            json['trust_score'],
      ),
      publishedAt: toStr(json['publishedAt'] ?? json['published_at'] ?? json['date']),
      stance: toStr(json['stance'] ?? json['polarity']),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'title': title,
      'source': source,
      'snippet': snippet,
      'url': url,
      'score': score,
      'publishedAt': publishedAt,
      'stance': stance,
    };
  }
}
