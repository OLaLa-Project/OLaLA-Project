import 'package:flutter_test/flutter_test.dart';
import 'package:olala_frontend/features/issue_chat/models/chat_message.dart';

void main() {
  group('ChatMessage.fromJson', () {
    test('parses standard payload', () {
      final message = ChatMessage.fromJson({
        'id': 'm1',
        'userId': 'u1',
        'username': 'alice',
        'content': 'hello',
        'timestamp': '2026-02-07T10:00:00.000Z',
        'reactionCount': 2,
        'isReactedByMe': true,
      });

      expect(message.id, 'm1');
      expect(message.userId, 'u1');
      expect(message.username, 'alice');
      expect(message.content, 'hello');
      expect(message.reactionCount, 2);
      expect(message.isReactedByMe, isTrue);
      expect(message.deliveryStatus, MessageDeliveryStatus.sent);
    });

    test('parses fallback keys and mixed value types', () {
      final message = ChatMessage.fromJson({
        'messageId': 123,
        'authorId': 456,
        'nickname': '익명',
        'message': 789,
        'createdAt': 1738922400000,
        'reactions': '10',
        'reacted': 1,
        'status': 'pending',
        'sendAttempts': '2',
      });

      expect(message.id, '123');
      expect(message.userId, '456');
      expect(message.content, '789');
      expect(message.reactionCount, 10);
      expect(message.isReactedByMe, isTrue);
      expect(message.deliveryStatus, MessageDeliveryStatus.pending);
      expect(message.sendAttempts, 2);
    });
  });
}
