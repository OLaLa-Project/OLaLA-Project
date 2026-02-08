class ChatMessage {
  final String id;
  final String userId;
  final String username;
  final String content;
  final DateTime timestamp;
  final bool isMine;
  final int reactionCount;
  final bool isReactedByMe;

  const ChatMessage({
    required this.id,
    required this.userId,
    required this.username,
    required this.content,
    required this.timestamp,
    required this.isMine,
    required this.reactionCount,
    required this.isReactedByMe,
  });

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    return ChatMessage(
      id: json['id'] as String,
      userId: json['userId'] as String,
      username: json['username'] as String,
      content: json['content'] as String,
      timestamp: DateTime.parse(json['timestamp'] as String),
      isMine: json['isMine'] as bool? ?? false,
      reactionCount: json['reactionCount'] as int? ?? 0,
      isReactedByMe: json['isReactedByMe'] as bool? ?? false,
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
    );
  }
}
