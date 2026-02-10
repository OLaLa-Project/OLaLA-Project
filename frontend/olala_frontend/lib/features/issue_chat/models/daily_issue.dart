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
    final rawPublishedAt =
        json['publishedAt'] ?? json['published_at'] ?? json['createdAt'];

    return DailyIssue(
      id: _readString(json, ['id', 'issueId', 'issue_id'], fallback: ''),
      title: _readString(json, ['title'], fallback: ''),
      summary: _readString(json, ['summary', 'subtitle'], fallback: ''),
      content: _readString(json, ['content', 'body'], fallback: ''),
      category: _readString(json, ['category', 'topic'], fallback: '기타'),
      participantCount:
          _readInt(json, [
            'participantCount',
            'participant_count',
            'participants',
          ]) ??
          0,
      publishedAt: _readDateTime(rawPublishedAt) ?? DateTime.now(),
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

String _readString(
  Map<String, dynamic> json,
  List<String> keys, {
  required String fallback,
}) {
  for (final key in keys) {
    final value = json[key];
    if (value is String) {
      final trimmed = value.trim();
      if (trimmed.isNotEmpty) return trimmed;
    } else if (value is num || value is bool) {
      return value.toString();
    }
  }
  return fallback;
}

int? _readInt(Map<String, dynamic> json, List<String> keys) {
  for (final key in keys) {
    final value = json[key];
    if (value is int) return value;
    if (value is num) return value.toInt();
    if (value is String) {
      final parsed = int.tryParse(value);
      if (parsed != null) return parsed;
    }
  }
  return null;
}

DateTime? _readDateTime(dynamic value) {
  if (value is DateTime) {
    return value.toLocal();
  }
  if (value is String) {
    try {
      return DateTime.parse(value).toLocal();
    } catch (_) {
      return null;
    }
  }
  if (value is int) {
    try {
      return DateTime.fromMillisecondsSinceEpoch(value).toLocal();
    } catch (_) {
      return null;
    }
  }
  return null;
}
