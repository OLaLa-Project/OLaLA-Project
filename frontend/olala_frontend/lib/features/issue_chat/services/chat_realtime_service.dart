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
  bool _isDisposed = false;
  bool _isSocketActive = false;
  String? _currentIssueId;

  Stream<Map<String, dynamic>> get events => _eventController.stream;
  bool get isConnected => _channel != null && _isSocketActive;

  void connect({
    required String issueId,
    required String userId,
    required String nickname,
    String? token,
    String? wsUrl,
  }) {
    if (_isDisposed) return;
    disconnect();

    final url = wsUrl ?? ApiEndpoints.chatWebSocket(issueId);
    _currentIssueId = issueId;
    _emit({'type': ChatEventType.connectionConnecting, 'issueId': issueId});

    try {
      final channel = WebSocketChannel.connect(Uri.parse(url));
      _channel = channel;
      _channelSubscription = channel.stream.listen(
        _handleIncoming,
        onError: (Object error) {
          _handleConnectionError(error);
        },
        onDone: _handleConnectionClosed,
      );

      _isSocketActive = true;
      final joinSent = _send({
        'type': ChatEventType.join,
        'issueId': issueId,
        'userId': userId,
        'nickname': nickname,
        if (token != null && token.isNotEmpty) 'token': token,
        'sentAt': DateTime.now().toIso8601String(),
      });

      if (!joinSent) {
        _handleConnectionError('join event send failed');
        return;
      }

      _emit({'type': ChatEventType.connectionOpen, 'issueId': issueId});
    } catch (e) {
      _handleConnectionError(e);
    }
  }

  bool sendMessage({
    required String issueId,
    required String clientId,
    required String userId,
    required String nickname,
    required String content,
    DateTime? sentAt,
  }) {
    return _send({
      'type': ChatEventType.messageCreate,
      'issueId': issueId,
      'clientId': clientId,
      'userId': userId,
      'nickname': nickname,
      'content': content,
      'sentAt': (sentAt ?? DateTime.now()).toIso8601String(),
    });
  }

  bool toggleReaction({
    required String issueId,
    required String messageId,
    required String userId,
  }) {
    return _send({
      'type': ChatEventType.reactionToggle,
      'issueId': issueId,
      'messageId': messageId,
      'userId': userId,
      'sentAt': DateTime.now().toIso8601String(),
    });
  }

  void disconnect() {
    _isSocketActive = false;
    _channelSubscription?.cancel();
    _channelSubscription = null;
    _channel?.sink.close();
    _channel = null;
  }

  void dispose() {
    if (_isDisposed) return;
    _isDisposed = true;
    disconnect();
    _eventController.close();
  }

  bool _send(Map<String, dynamic> payload) {
    final channel = _channel;
    if (channel == null || !_isSocketActive) {
      _emit({
        'type': ChatEventType.error,
        'message': '실시간 연결이 끊어진 상태입니다.',
        'issueId': _currentIssueId,
      });
      return false;
    }
    try {
      channel.sink.add(jsonEncode(payload));
      return true;
    } catch (e) {
      _emit({
        'type': ChatEventType.connectionError,
        'error': e.toString(),
        'issueId': _currentIssueId,
      });
      return false;
    }
  }

  void _handleConnectionError(Object error) {
    _isSocketActive = false;
    _emit({
      'type': ChatEventType.connectionError,
      'error': error.toString(),
      'issueId': _currentIssueId,
    });
    disconnect();
  }

  void _handleConnectionClosed() {
    _isSocketActive = false;
    _emit({'type': ChatEventType.connectionClosed, 'issueId': _currentIssueId});
    disconnect();
  }

  void _handleIncoming(dynamic data) {
    final decoded = _decodePayload(data);
    if (decoded == null) {
      _emit({'type': 'message.raw', 'raw': data.toString()});
      return;
    }

    if (decoded is List) {
      for (final item in decoded) {
        if (item is Map) {
          _emitEvent(Map<String, dynamic>.from(item));
        }
      }
      return;
    }

    if (decoded is Map<String, dynamic>) {
      _emitEvent(decoded);
      return;
    }

    if (decoded is Map) {
      _emitEvent(Map<String, dynamic>.from(decoded));
    }
  }

  void _emitEvent(Map<String, dynamic> payload) {
    if (payload.containsKey('type')) {
      _emit(payload);
      return;
    }

    if (payload.containsKey('content') && payload.containsKey('userId')) {
      _emit({'type': ChatEventType.messageCreated, 'message': payload});
      return;
    }

    _emit({'type': 'message.raw', 'raw': payload});
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

  void _emit(Map<String, dynamic> event) {
    if (_isDisposed || _eventController.isClosed) return;
    _eventController.add(event);
  }
}
