import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

class _Connection {
  _Connection({
    required this.socket,
    required this.issueId,
  });

  final WebSocket socket;
  final String issueId;
  String? userId;
  String? nickname;
}

class _ChatStore {
  final Map<String, List<Map<String, dynamic>>> messages = {};
  final Map<String, Set<String>> reactionsByMessage = {};

  List<Map<String, dynamic>> getMessages(String issueId, int limit) {
    final list = messages[issueId] ?? [];
    if (list.length <= limit) return List<Map<String, dynamic>>.from(list);
    return List<Map<String, dynamic>>.from(
      list.sublist(list.length - limit),
    );
  }

  Map<String, dynamic> addMessage({
    required String issueId,
    required String messageId,
    required String userId,
    required String username,
    required String content,
    required String timestamp,
  }) {
    final message = {
      'id': messageId,
      'issueId': issueId,
      'userId': userId,
      'username': username,
      'content': content,
      'timestamp': timestamp,
      'reactionCount': 0,
    };
    messages.putIfAbsent(issueId, () => []).add(message);
    return message;
  }

  int toggleReaction({
    required String messageId,
    required String userId,
  }) {
    final set = reactionsByMessage.putIfAbsent(messageId, () => <String>{});
    if (set.contains(userId)) {
      set.remove(userId);
    } else {
      set.add(userId);
    }
    return set.length;
  }

  bool isReactedByUser({
    required String messageId,
    required String userId,
  }) {
    final set = reactionsByMessage[messageId];
    if (set == null) return false;
    return set.contains(userId);
  }
}

final _random = Random();
final _store = _ChatStore();
final Map<String, Set<_Connection>> _rooms = {};
final String _webRoot = Directory.current.uri
    .resolve('build/web/')
    .toFilePath();

Future<void> main(List<String> args) async {
  final port = args.isNotEmpty ? int.tryParse(args.first) ?? 8080 : 8080;
  final server = await HttpServer.bind(InternetAddress.anyIPv4, port);
  stdout.writeln('Local chat server listening on http://0.0.0.0:$port');

  await for (final request in server) {
    if (request.method == 'OPTIONS') {
      _respondCors(request.response);
      request.response.statusCode = HttpStatus.noContent;
      await request.response.close();
      continue;
    }

    final path = request.uri.path;
    final segments = request.uri.pathSegments;

    if (request.method == 'GET' && path == '/v1/issues/today') {
      _respondCors(request.response);
      request.response.headers.contentType = ContentType.json;
      request.response.write(
        jsonEncode(_buildTodayIssue()),
      );
      await request.response.close();
      continue;
    }

    if (request.method == 'GET') {
      final served = await _tryServeWeb(request);
      if (served) {
        continue;
      }
    }

    if (segments.length >= 4 &&
        segments[0] == 'v1' &&
        segments[1] == 'chat' &&
        segments[2] == 'messages' &&
        request.method == 'GET') {
      final issueId = segments[3];
      final limit = int.tryParse(request.uri.queryParameters['limit'] ?? '') ??
          50;
      final list = _store.getMessages(issueId, limit);
      _respondCors(request.response);
      request.response.headers.contentType = ContentType.json;
      request.response.write(jsonEncode(list));
      await request.response.close();
      continue;
    }

    if (segments.length >= 3 &&
        segments[0] == 'v1' &&
        segments[1] == 'chat' &&
        WebSocketTransformer.isUpgradeRequest(request)) {
      final issueId = segments[2];
      await _handleWebSocket(request, issueId);
      continue;
    }

    _respondCors(request.response);
    request.response.statusCode = HttpStatus.notFound;
    request.response.write('Not Found');
    await request.response.close();
  }
}

Future<void> _handleWebSocket(HttpRequest request, String issueId) async {
  final socket = await WebSocketTransformer.upgrade(request);
  final connection = _Connection(socket: socket, issueId: issueId);
  _rooms.putIfAbsent(issueId, () => <_Connection>{}).add(connection);
  _broadcastPresence(issueId);

  socket.listen(
    (dynamic data) {
      final payload = _decodePayload(data);
      if (payload is! Map<String, dynamic>) {
        return;
      }

      final type = payload['type'] as String? ?? '';
      switch (type) {
        case 'join':
          connection.userId = payload['userId']?.toString();
          connection.nickname = payload['nickname']?.toString();
          _broadcastPresence(issueId);
          return;
        case 'message.create':
          _handleMessageCreate(connection, payload);
          return;
        case 'reaction.toggle':
          _handleReactionToggle(connection, payload);
          return;
        default:
          _send(connection.socket, {
            'type': 'error',
            'issueId': issueId,
            'message': 'Unknown event type: $type',
          });
          return;
      }
    },
    onDone: () {
      _removeConnection(connection);
    },
    onError: (_) {
      _removeConnection(connection);
    },
  );
}

void _handleMessageCreate(_Connection connection, Map<String, dynamic> payload) {
  final issueId = connection.issueId;
  final content = payload['content']?.toString().trim() ?? '';
  final userId = payload['userId']?.toString() ?? connection.userId;
  final nickname = payload['nickname']?.toString() ?? connection.nickname;
  final clientId = payload['clientId']?.toString();

  if (content.isEmpty || userId == null || nickname == null) {
    _send(connection.socket, {
      'type': 'error',
      'issueId': issueId,
      'message': 'Invalid message payload',
    });
    return;
  }

  final messageId =
      'msg_${DateTime.now().millisecondsSinceEpoch}_${_random.nextInt(9999)}';
  final timestamp = DateTime.now().toUtc().toIso8601String();
  final message = _store.addMessage(
    issueId: issueId,
    messageId: messageId,
    userId: userId,
    username: nickname,
    content: content,
    timestamp: timestamp,
  );

  _send(connection.socket, {
    'type': 'message.ack',
    'issueId': issueId,
    'clientId': clientId,
    'serverId': messageId,
    'timestamp': timestamp,
    'status': 'ok',
  });

  _broadcast(issueId, {
    'type': 'message.created',
    'issueId': issueId,
    'serverAt': timestamp,
    if (clientId != null) 'clientId': clientId,
    'message': message,
  });
}

void _handleReactionToggle(_Connection connection, Map<String, dynamic> payload) {
  final issueId = connection.issueId;
  final messageId = payload['messageId']?.toString();
  final userId = payload['userId']?.toString() ?? connection.userId;

  if (messageId == null || userId == null) {
    _send(connection.socket, {
      'type': 'error',
      'issueId': issueId,
      'message': 'Invalid reaction payload',
    });
    return;
  }

  final count = _store.toggleReaction(
    messageId: messageId,
    userId: userId,
  );

  _broadcastPerConnection(issueId, (conn) {
    final isReactedByMe = conn.userId == null
        ? false
        : _store.isReactedByUser(messageId: messageId, userId: conn.userId!);
    return {
      'type': 'reaction.updated',
      'issueId': issueId,
      'messageId': messageId,
      'count': count,
      'isReactedByMe': isReactedByMe,
      'serverAt': DateTime.now().toUtc().toIso8601String(),
    };
  });
}

void _broadcastPresence(String issueId) {
  final count = _rooms[issueId]?.length ?? 0;
  _broadcast(issueId, {
    'type': 'presence',
    'issueId': issueId,
    'onlineCount': count,
    'serverAt': DateTime.now().toUtc().toIso8601String(),
  });
}

void _broadcast(String issueId, Map<String, dynamic> payload) {
  final room = _rooms[issueId];
  if (room == null) return;
  for (final connection in room) {
    _send(connection.socket, payload);
  }
}

void _broadcastPerConnection(
  String issueId,
  Map<String, dynamic> Function(_Connection connection) builder,
) {
  final room = _rooms[issueId];
  if (room == null) return;
  for (final connection in room) {
    _send(connection.socket, builder(connection));
  }
}

void _removeConnection(_Connection connection) {
  final room = _rooms[connection.issueId];
  room?.remove(connection);
  connection.socket.close();
  if (room != null && room.isEmpty) {
    _rooms.remove(connection.issueId);
  }
  _broadcastPresence(connection.issueId);
}

void _send(WebSocket socket, Map<String, dynamic> payload) {
  socket.add(jsonEncode(payload));
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

void _respondCors(HttpResponse response) {
  response.headers
    ..set('Access-Control-Allow-Origin', '*')
    ..set('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
    ..set('Access-Control-Allow-Headers', 'Content-Type, Authorization');
}

Map<String, dynamic> _buildTodayIssue() {
  final now = DateTime.now();
  final issueId =
      'issue_${now.year}${now.month.toString().padLeft(2, '0')}${now.day.toString().padLeft(2, '0')}';

  final count = _rooms[issueId]?.length ?? 0;

  return {
    'id': issueId,
    'title': '2025년 AI 윤리 규제안, 국회 본회의 통과',
    'summary':
        '인공지능 개발 및 활용에 대한 윤리적 기준을 명시한 법안이 국회를 통과했습니다. 이번 법안은 AI 시스템의 투명성, 설명 가능성, 공정성을 강화하는 내용을 담고 있습니다.',
    'content': '현장 데모용 기사 본문입니다. 서버에서 실제 데이터를 연결하면'
        ' 이 내용이 실제 기사 전문으로 대체됩니다.',
    'category': '정치',
    'participantCount': count,
    'publishedAt': now.subtract(const Duration(hours: 2)).toIso8601String(),
  };
}

Future<bool> _tryServeWeb(HttpRequest request) async {
  final path = request.uri.path;
  if (path.startsWith('/v1/')) {
    return false;
  }

  final requested = path == '/' ? '/index.html' : path;
  final filePath = _webRoot + requested;
  final file = File(filePath);

  if (await file.exists()) {
    await _sendFile(request.response, file);
    return true;
  }

  final indexFile = File(_webRoot + 'index.html');
  if (await indexFile.exists()) {
    await _sendFile(request.response, indexFile);
    return true;
  }

  return false;
}

Future<void> _sendFile(HttpResponse response, File file) async {
  response.headers.contentType = _contentTypeFor(file.path);
  await response.addStream(file.openRead());
  await response.close();
}

ContentType _contentTypeFor(String path) {
  if (path.endsWith('.html')) return ContentType.html;
  if (path.endsWith('.js')) return ContentType('application', 'javascript');
  if (path.endsWith('.css')) return ContentType('text', 'css');
  if (path.endsWith('.json')) return ContentType.json;
  if (path.endsWith('.png')) return ContentType('image', 'png');
  if (path.endsWith('.jpg') || path.endsWith('.jpeg')) {
    return ContentType('image', 'jpeg');
  }
  if (path.endsWith('.svg')) return ContentType('image', 'svg+xml');
  if (path.endsWith('.wasm')) return ContentType('application', 'wasm');
  return ContentType('application', 'octet-stream');
}
