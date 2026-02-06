import 'dart:async';
import 'dart:convert';

import 'package:web_socket_channel/web_socket_channel.dart';

import '../../../shared/network/api_endpoints.dart';
import '../models/chat_event.dart';

class ChatRealtimeService {
  final StreamController<Map<String, dynamic>> _eventController =
      StreamController.broadcast();

  WebSocketChannel? _channel;
  StreamSubscription? _channelSubscription;

  Stream<Map<String, dynamic>> get events => _eventController.stream;
  bool get isConnected => _channel != null;

  void connect({
    required String issueId,
    required String userId,
    required String nickname,
    String? token,
    String? wsUrl,
  }) {
    disconnect();

    final url = wsUrl ?? ApiEndpoints.chatWebSocket(issueId);
    _eventController.add({'type': ChatEventType.connectionConnecting});

    _channel = WebSocketChannel.connect(Uri.parse(url));

    _channelSubscription = _channel!.stream.listen(
      _handleIncoming,
      onError: (Object error) {
        _eventController.add({
          'type': ChatEventType.connectionError,
          'error': error.toString(),
        });
        disconnect();
      },
      onDone: () {
        _eventController.add({'type': ChatEventType.connectionClosed});
        disconnect();
      },
    );

    _eventController.add({'type': ChatEventType.connectionOpen});
    _send({
      'type': ChatEventType.join,
      'issueId': issueId,
      'userId': userId,
      'nickname': nickname,
      if (token != null) 'token': token,
      'sentAt': DateTime.now().toIso8601String(),
    });
  }

  void sendMessage({
    required String issueId,
    required String clientId,
    required String userId,
    required String nickname,
    required String content,
    DateTime? sentAt,
  }) {
    _send({
      'type': ChatEventType.messageCreate,
      'issueId': issueId,
      'clientId': clientId,
      'userId': userId,
      'nickname': nickname,
      'content': content,
      'sentAt': (sentAt ?? DateTime.now()).toIso8601String(),
    });
  }

  void toggleReaction({
    required String issueId,
    required String messageId,
    required String userId,
  }) {
    _send({
      'type': ChatEventType.reactionToggle,
      'issueId': issueId,
      'messageId': messageId,
      'userId': userId,
      'sentAt': DateTime.now().toIso8601String(),
    });
  }

  void disconnect() {
    _channelSubscription?.cancel();
    _channelSubscription = null;
    _channel?.sink.close();
    _channel = null;
  }

  void dispose() {
    disconnect();
    _eventController.close();
  }

  void _send(Map<String, dynamic> payload) {
    if (_channel == null) return;
    _channel!.sink.add(jsonEncode(payload));
  }

  void _handleIncoming(dynamic data) {
    final decoded = _decodePayload(data);
    if (decoded == null) {
      _eventController.add({
        'type': 'message.raw',
        'raw': data.toString(),
      });
      return;
    }

    if (decoded is List) {
      for (final item in decoded) {
        if (item is Map<String, dynamic>) {
          _emitEvent(item);
        }
      }
      return;
    }

    if (decoded is Map<String, dynamic>) {
      _emitEvent(decoded);
    }
  }

  void _emitEvent(Map<String, dynamic> payload) {
    if (payload.containsKey('type')) {
      _eventController.add(payload);
      return;
    }

    if (payload.containsKey('content') && payload.containsKey('userId')) {
      _eventController.add({
        'type': ChatEventType.messageCreated,
        'message': payload,
      });
      return;
    }

    _eventController.add({
      'type': 'message.raw',
      'raw': payload,
    });
  }

  dynamic _decodePayload(dynamic data) {
    if (data is String) {
      try {
        return jsonDecode(data);
      } catch (_) {
        return null;
      }
    }

    if (data is List<int>) {
      try {
        return jsonDecode(utf8.decode(data));
      } catch (_) {
        return null;
      }
    }

    return null;
  }
}
