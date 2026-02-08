import 'dart:async';

import 'package:flutter/material.dart';
import 'package:get/get.dart';

import 'models/daily_issue.dart';
import 'models/chat_message.dart';
import 'models/chat_user.dart';
import 'models/chat_event.dart';
import 'repository/api_issue_repository.dart';
import 'repository/issue_repository.dart';
import '../../shared/storage/local_storage.dart';
import 'services/chat_realtime_service.dart';
import '../../shared/network/api_endpoints.dart';

/// 채팅 화면 컨트롤러
class IssueChatController extends GetxController {
  final DailyIssue issue;
  final IssueRepository _repository;
  final ChatRealtimeService _realtimeService = ChatRealtimeService();

  IssueChatController({
    required this.issue,
    IssueRepository? repository,
  }) : _repository = repository ??
            ApiIssueRepository(baseUrl: ApiEndpoints.apiBase);

  // 상태
  final RxList<ChatMessage> messages = <ChatMessage>[].obs;
  final RxBool isLoading = false.obs;
  final RxBool isSending = false.obs;
  final Rxn<ChatUser> currentUser = Rxn<ChatUser>();
  final RxBool isConnected = false.obs;
  final RxBool isReconnecting = false.obs;

  // 텍스트 입력
  final TextEditingController textController = TextEditingController();
  final ScrollController scrollController = ScrollController();

  StreamSubscription<Map<String, dynamic>>? _realtimeSubscription;
  Timer? _reconnectTimer;
  int _reconnectAttempts = 0;
  bool _shouldReconnect = true;

  @override
  void onInit() {
    super.onInit();
    _bootstrap();
  }

  Future<void> _bootstrap() async {
    await _initUser();
    await _loadChatHistory();
    _connectRealtime();
  }

  /// 익명 사용자 초기화
  Future<void> _initUser() async {
    final stored = await LocalStorage.getAnonymousUser();
    if (stored != null) {
      currentUser.value = stored;
    } else {
      final newUser = ChatUser.anonymous();
      await LocalStorage.saveAnonymousUser(newUser);
      currentUser.value = newUser;
    }
  }

  /// 채팅 히스토리 로드
  Future<void> _loadChatHistory() async {
    isLoading.value = true;
    try {
      final history = await _repository.getChatHistory(issue.id);

      // isMine 설정
      final updatedHistory = history.map((msg) {
        return msg.copyWith(
          isMine: msg.userId == currentUser.value?.id,
        );
      }).toList();

      messages.assignAll(updatedHistory);
      _scrollToBottom();
    } catch (e) {
      Get.snackbar(
        '오류',
        '메시지를 불러올 수 없습니다.',
        snackPosition: SnackPosition.BOTTOM,
      );
    } finally {
      isLoading.value = false;
    }
  }

  /// 메시지 전송
  Future<void> sendMessage() async {
    final content = textController.text.trim();
    if (content.isEmpty || currentUser.value == null) return;

    if (!isConnected.value) {
      Get.snackbar(
        '연결 끊김',
        '네트워크를 확인하고 잠시 후 다시 시도해주세요.',
        snackPosition: SnackPosition.BOTTOM,
      );
      _scheduleReconnect();
      return;
    }

    isSending.value = true;
    final clientId = 'c_${DateTime.now().millisecondsSinceEpoch}';

    // Optimistic update
    final tempMessage = ChatMessage(
      id: clientId,
      userId: currentUser.value!.id,
      username: currentUser.value!.nickname,
      content: content,
      timestamp: DateTime.now(),
      isMine: true,
      reactionCount: 0,
      isReactedByMe: false,
    );

    messages.add(tempMessage);
    textController.clear();
    _scrollToBottom();

    try {
      _realtimeService.sendMessage(
        issueId: issue.id,
        clientId: clientId,
        userId: currentUser.value!.id,
        nickname: currentUser.value!.nickname,
        content: content,
        sentAt: tempMessage.timestamp,
      );
    } catch (e) {
      // 전송 실패 시 임시 메시지 제거
      messages.removeWhere((m) => m.id == tempMessage.id);
      Get.snackbar(
        '전송 실패',
        '메시지를 전송할 수 없습니다.',
        snackPosition: SnackPosition.BOTTOM,
      );
    } finally {
      isSending.value = false;
    }
  }

  /// 반응 토글
  Future<void> toggleReaction(String messageId) async {
    try {
      if (!isConnected.value || currentUser.value == null) {
        Get.snackbar(
          '연결 끊김',
          '네트워크를 확인하고 잠시 후 다시 시도해주세요.',
          snackPosition: SnackPosition.BOTTOM,
        );
        _scheduleReconnect();
        return;
      }

      final index = messages.indexWhere((m) => m.id == messageId);
      if (index == -1) return;

      final message = messages[index];
      final newIsReacted = !message.isReactedByMe;
      final newCount = newIsReacted
          ? message.reactionCount + 1
          : message.reactionCount - 1;

      // Optimistic update
      messages[index] = message.copyWith(
        isReactedByMe: newIsReacted,
        reactionCount: newCount.clamp(0, 9999),
      );

      _realtimeService.toggleReaction(
        issueId: issue.id,
        messageId: messageId,
        userId: currentUser.value!.id,
      );
    } catch (e) {
      Get.snackbar(
        '오류',
        '반응을 추가할 수 없습니다.',
        snackPosition: SnackPosition.BOTTOM,
      );
    }
  }

  /// 스크롤을 맨 아래로
  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (scrollController.hasClients) {
        scrollController.animateTo(
          scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _connectRealtime() {
    final user = currentUser.value;
    if (user == null) return;

    _realtimeSubscription?.cancel();
    _realtimeService.connect(
      issueId: issue.id,
      userId: user.id,
      nickname: user.nickname,
    );

    _realtimeSubscription = _realtimeService.events.listen((event) {
      _handleRealtimeEvent(event);
    });
  }

  void _handleRealtimeEvent(Map<String, dynamic> event) {
    final eventIssueId = event['issueId'];
    if (eventIssueId is String && eventIssueId != issue.id) {
      return;
    }
    final type = event['type'] as String? ?? '';

    switch (type) {
      case ChatEventType.connectionConnecting:
        isConnected.value = false;
        isReconnecting.value = true;
        return;
      case ChatEventType.connectionOpen:
        isConnected.value = true;
        isReconnecting.value = false;
        _reconnectAttempts = 0;
        return;
      case ChatEventType.connectionClosed:
      case ChatEventType.connectionError:
        isConnected.value = false;
        _scheduleReconnect();
        return;
      case ChatEventType.messageCreated:
        _handleIncomingMessage(event);
        return;
      case ChatEventType.messageAck:
        _handleMessageAck(event);
        return;
      case ChatEventType.reactionUpdated:
        _handleReactionUpdate(event);
        return;
      case ChatEventType.error:
        _handleRealtimeError(event);
        return;
      default:
        return;
    }
  }

  void _handleIncomingMessage(Map<String, dynamic> event) {
    final payload = event['message'] ??
        event['payload'] ??
        event['data'];
    final raw = payload is Map<String, dynamic>
        ? payload
        : (event.containsKey('content') && event.containsKey('userId')
            ? event
            : null);
    if (raw == null) return;

    final normalized = _normalizeMessagePayload(
      raw,
      fallbackTimestamp: event['serverAt'] ?? event['timestamp'],
    );
    final incoming = ChatMessage.fromJson(normalized).copyWith(
      isMine: normalized['userId'] == currentUser.value?.id,
    );

    final clientId = event['clientId'] as String? ??
        normalized['clientId'] as String?;

    _upsertMessage(incoming, clientId: clientId);
  }

  void _handleMessageAck(Map<String, dynamic> event) {
    final clientId = event['clientId'] as String? ??
        event['tempId'] as String?;
    final serverId = event['serverId'] as String? ??
        event['messageId'] as String? ??
        (event['message'] is Map<String, dynamic>
            ? (event['message']['id'] as String?)
            : null);
    final timestamp = _parseTimestamp(
      event['timestamp'] ?? event['sentAt'] ?? event['createdAt'],
    );

    if (clientId == null) return;
    final index = messages.indexWhere((m) => m.id == clientId);
    if (index == -1) return;

    messages[index] = messages[index].copyWith(
      id: serverId ?? messages[index].id,
      timestamp: timestamp ?? messages[index].timestamp,
    );
  }

  void _handleReactionUpdate(Map<String, dynamic> event) {
    final messageId = event['messageId'] as String? ?? event['id'] as String?;
    if (messageId == null) return;

    final index = messages.indexWhere((m) => m.id == messageId);
    if (index == -1) return;

    final count = event['count'];
    final isReacted = event['isReactedByMe'];

    messages[index] = messages[index].copyWith(
      reactionCount: count is int ? count : messages[index].reactionCount,
      isReactedByMe: isReacted is bool ? isReacted : messages[index].isReactedByMe,
    );
  }

  void _upsertMessage(ChatMessage message, {String? clientId}) {
    if (clientId != null) {
      final clientIndex = messages.indexWhere((m) => m.id == clientId);
      if (clientIndex != -1) {
        messages[clientIndex] = message;
        return;
      }
    }

    final index = messages.indexWhere((m) => m.id == message.id);
    if (index != -1) {
      messages[index] = message;
      return;
    }

    messages.add(message);
    _scrollToBottom();
  }

  Map<String, dynamic> _normalizeMessagePayload(
    Map<String, dynamic> raw, {
    dynamic fallbackTimestamp,
  }) {
    final normalized = Map<String, dynamic>.from(raw);

    final candidate = normalized['timestamp'] ??
        normalized['sentAt'] ??
        normalized['createdAt'] ??
        fallbackTimestamp;

    if (candidate != null) {
      normalized['timestamp'] = _normalizeTimestamp(candidate);
    }

    if (normalized['username'] == null && normalized['nickname'] != null) {
      normalized['username'] = normalized['nickname'];
    }

    if (normalized['id'] == null && normalized['messageId'] != null) {
      normalized['id'] = normalized['messageId'];
    }

    return normalized;
  }

  String? _normalizeTimestamp(dynamic value) {
    if (value is String) {
      return value;
    }
    if (value is int) {
      try {
        return DateTime.fromMillisecondsSinceEpoch(value).toIso8601String();
      } catch (_) {
        return null;
      }
    }
    return null;
  }

  DateTime? _parseTimestamp(dynamic value) {
    if (value is String) {
      try {
        return DateTime.parse(value);
      } catch (_) {
        return null;
      }
    }
    if (value is int) {
      try {
        return DateTime.fromMillisecondsSinceEpoch(value);
      } catch (_) {
        return null;
      }
    }
    return null;
  }

  void _handleRealtimeError(Map<String, dynamic> event) {
    final message = event['message'] as String? ??
        event['error'] as String? ??
        '서버 오류가 발생했습니다.';
    Get.snackbar(
      '오류',
      message,
      snackPosition: SnackPosition.BOTTOM,
    );
  }

  void _scheduleReconnect() {
    if (!_shouldReconnect) return;
    if (_reconnectTimer?.isActive ?? false) return;

    _reconnectAttempts = (_reconnectAttempts + 1).clamp(1, 6);
    final delay = Duration(seconds: 2 * _reconnectAttempts);
    isReconnecting.value = true;

    _reconnectTimer = Timer(delay, _connectRealtime);
  }

  @override
  void onClose() {
    _shouldReconnect = false;
    _reconnectTimer?.cancel();
    _realtimeSubscription?.cancel();
    _realtimeService.dispose();
    textController.dispose();
    scrollController.dispose();
    super.onClose();
  }
}
