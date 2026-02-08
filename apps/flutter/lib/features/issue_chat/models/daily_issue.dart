class DailyIssue {
  final String id;
  final String title;
  final String summary;
  final String content;
  final String category;
  final int participantCount;
  final DateTime publishedAt;

  const DailyIssue({
    required this.id,
    required this.title,
    required this.summary,
    required this.content,
    required this.category,
    required this.participantCount,
    required this.publishedAt,
  });

  factory DailyIssue.fromJson(Map<String, dynamic> json) {
    return DailyIssue(
      id: json['id'] as String,
      title: json['title'] as String,
      summary: json['summary'] as String,
      content: json['content'] as String? ?? '',
      category: json['category'] as String,
      participantCount: json['participantCount'] as int,
      publishedAt: DateTime.parse(json['publishedAt'] as String),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'title': title,
      'summary': summary,
      'content': content,
      'category': category,
      'participantCount': participantCount,
      'publishedAt': publishedAt.toIso8601String(),
    };
  }

  DailyIssue copyWith({
    String? id,
    String? title,
    String? summary,
    String? content,
    String? category,
    int? participantCount,
    DateTime? publishedAt,
  }) {
    return DailyIssue(
      id: id ?? this.id,
      title: title ?? this.title,
      summary: summary ?? this.summary,
      content: content ?? this.content,
      category: category ?? this.category,
      participantCount: participantCount ?? this.participantCount,
      publishedAt: publishedAt ?? this.publishedAt,
    );
  }
}
