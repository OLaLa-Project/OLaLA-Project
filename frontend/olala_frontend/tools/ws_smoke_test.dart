import 'dart:convert';
import 'dart:io';

Future<void> main(List<String> args) async {
  final port = args.isNotEmpty ? args.first : '8080';
  final issueId = args.length > 1 ? args[1] : 'issue_test';
  final uri = Uri.parse('ws://127.0.0.1:$port/v1/chat/$issueId');
  late final WebSocket socket;
  try {
    socket = await WebSocket.connect(uri.toString())
        .timeout(const Duration(seconds: 2));
  } catch (e) {
    stderr.writeln('WebSocket connect failed: $e');
    exit(1);
  }

  socket.listen((data) {
    stdout.writeln('<= $data');
  });

  socket.add(jsonEncode({
    'type': 'join',
    'issueId': 'issue_test',
    'userId': 'tester_1',
    'nickname': '테스터',
    'sentAt': DateTime.now().toUtc().toIso8601String(),
  }));

  await Future.delayed(const Duration(milliseconds: 200));

  socket.add(jsonEncode({
    'type': 'message.create',
    'issueId': 'issue_test',
    'clientId': 'c_test_1',
    'userId': 'tester_1',
    'nickname': '테스터',
    'content': '연결 테스트 메시지',
    'sentAt': DateTime.now().toUtc().toIso8601String(),
  }));

  await Future.delayed(const Duration(seconds: 1));
  socket.close();
  exit(0);
}
