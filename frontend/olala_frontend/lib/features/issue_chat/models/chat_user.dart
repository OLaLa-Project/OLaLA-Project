import 'dart:math';
import 'package:uuid/uuid.dart';

class ChatUser {
  final String id;
  final String nickname;
  final String avatarColor;

  const ChatUser({
    required this.id,
    required this.nickname,
    required this.avatarColor,
  });

  /// 익명 사용자 생성 (UUID + 랜덤 닉네임 + 랜덤 색상)
  factory ChatUser.anonymous() {
    final uuid = const Uuid().v4();
    final randomNum = Random().nextInt(9999);
    final nickname = '익명$randomNum';

    // 랜덤 아바타 색상 (파스텔톤)
    const colors = [
      'FFAEC9', // Pink
      'A0C4FF', // Blue
      'BDB2FF', // Purple
      'FFC6FF', // Magenta
      'CAFFBF', // Green
      'FFD6A5', // Orange
    ];
    final avatarColor = colors[Random().nextInt(colors.length)];

    return ChatUser(
      id: uuid,
      nickname: nickname,
      avatarColor: avatarColor,
    );
  }

  factory ChatUser.fromJson(Map<String, dynamic> json) {
    return ChatUser(
      id: json['id'] as String,
      nickname: json['nickname'] as String,
      avatarColor: json['avatarColor'] as String,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'nickname': nickname,
      'avatarColor': avatarColor,
    };
  }

  ChatUser copyWith({
    String? id,
    String? nickname,
    String? avatarColor,
  }) {
    return ChatUser(
      id: id ?? this.id,
      nickname: nickname ?? this.nickname,
      avatarColor: avatarColor ?? this.avatarColor,
    );
  }
}
