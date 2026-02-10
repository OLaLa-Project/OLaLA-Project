enum MessageDeliveryStatus { pending, sent, failed }

class ChatMessage {
  final String id;
  final String userId;
  final String username;
  final String content;
  final DateTime timestamp;
  final bool isMine;
  final int reactionCount;
  final bool isReactedByMe;
  final MessageDeliveryStatus deliveryStatus;
  final int sendAttempts;

  const ChatMessage({
    required this.id,
    required this.userId,
    required this.username,
    required this.content,
    required this.timestamp,
    required this.isMine,
    required this.reactionCount,
    required this.isReactedByMe,
    this.deliveryStatus = MessageDeliveryStatus.sent,
    this.sendAttempts = 0,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    final rawTimestamp =
        json['timestamp'] ?? json['createdAt'] ?? json['sentAt'];
    final timestamp = _parseDateTime(rawTimestamp) ?? DateTime.now();
    final rawReactionCount = json['reactionCount'] ?? json['reactions'];
    final rawDeliveryStatus = json['deliveryStatus'] ?? json['status'];

    return ChatMessage(
      id: _asString(
        json['id'] ?? json['messageId'] ?? json['clientId'],
        fallback: '',
      ),
      userId: _asString(json['userId'] ?? json['authorId'], fallback: ''),
      username: _asString(
        json['username'] ?? json['nickname'] ?? json['authorName'],
        fallback: '익명',
      ),
      content: _asString(json['content'] ?? json['message'], fallback: ''),
      timestamp: timestamp,
      isMine: _asBool(json['isMine']) ?? false,
      reactionCount: _asInt(rawReactionCount) ?? 0,
      isReactedByMe: _asBool(json['isReactedByMe'] ?? json['reacted']) ?? false,
      deliveryStatus: _deliveryStatusFrom(rawDeliveryStatus),
      sendAttempts: _asInt(json['sendAttempts']) ?? 0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'userId': userId,
      'username': username,
      'content': content,
      'timestamp': timestamp.toIso8601String(),
      'isMine': isMine,
      'reactionCount': reactionCount,
      'isReactedByMe': isReactedByMe,
      'deliveryStatus': deliveryStatus.name,
      'sendAttempts': sendAttempts,
    };
  }

  ChatMessage copyWith({
    String? id,
    String? userId,
    String? username,
    String? content,
    DateTime? timestamp,
    bool? isMine,
    int? reactionCount,
    bool? isReactedByMe,
    MessageDeliveryStatus? deliveryStatus,
    int? sendAttempts,
  }) {
    return ChatMessage(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      username: username ?? this.username,
      content: content ?? this.content,
      timestamp: timestamp ?? this.timestamp,
      isMine: isMine ?? this.isMine,
      reactionCount: reactionCount ?? this.reactionCount,
      isReactedByMe: isReactedByMe ?? this.isReactedByMe,
      deliveryStatus: deliveryStatus ?? this.deliveryStatus,
      sendAttempts: sendAttempts ?? this.sendAttempts,
    );
  }
}

String _asString(dynamic value, {required String fallback}) {
  if (value is String) {
    final trimmed = value.trim();
    if (trimmed.isNotEmpty) return trimmed;
    return fallback;
  }
  if (value is num || value is bool) {
    return value.toString();
  }
  return fallback;
}

int? _asInt(dynamic value) {
  if (value is int) return value;
  if (value is num) return value.toInt();
  if (value is String) return int.tryParse(value);
  return null;
}

bool? _asBool(dynamic value) {
  if (value is bool) return value;
  if (value is String) {
    final normalized = value.toLowerCase();
    if (normalized == 'true') return true;
    if (normalized == 'false') return false;
  }
  if (value is num) {
    if (value == 1) return true;
    if (value == 0) return false;
  }
  return null;
}

DateTime? _parseDateTime(dynamic value) {
  if (value is DateTime) return value;
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

MessageDeliveryStatus _deliveryStatusFrom(dynamic value) {
  if (value is String) {
    switch (value) {
      case 'pending':
        return MessageDeliveryStatus.pending;
      case 'failed':
        return MessageDeliveryStatus.failed;
      case 'sent':
      default:
        return MessageDeliveryStatus.sent;
    }
  }
  return MessageDeliveryStatus.sent;
}
