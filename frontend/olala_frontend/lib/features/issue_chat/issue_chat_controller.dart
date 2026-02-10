import 'dart:async';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:get/get.dart';

import '../../shared/network/api_endpoints.dart';
import '../../shared/storage/local_storage.dart';
import 'models/chat_event.dart';
import 'models/chat_message.dart';
import 'models/chat_user.dart';
import 'models/daily_issue.dart';
import 'repository/api_issue_repository.dart';
import 'repository/issue_repository.dart';
import 'repository/issue_repository_exception.dart';
import 'services/chat_realtime_service.dart';

/// 채팅 화면 컨트롤러
class IssueChatController extends GetxController {
  IssueChatController({
    required this.issue,
    IssueRepository? repository,
    ChatRealtimeService? realtimeService,
    String? authToken,
  }) : _repository =
           repository ?? ApiIssueRepository(baseUrl: ApiEndpoints.apiBase),
       _realtimeService = realtimeService ?? ChatRealtimeService(),
       _authToken = authToken;

  static const Duration _ackTimeout = Duration(seconds: 8);
  static const int _maxSendAttempts = 3;
  static const int _maxReconnectAttempts = 8;
  static const int _maxMessageLength = 500;

  final DailyIssue issue;
  final IssueRepository _repository;
  final ChatRealtimeService _realtimeService;
  final String? _authToken;
  final Random _random = Random();

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
  final Map<String, _PendingMessage> _pendingMessages = {};

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
      return;
    }

    final newUser = ChatUser.anonymous();
    await LocalStorage.saveAnonymousUser(newUser);
    currentUser.value = newUser;
  }

  /// 채팅 히스토리 로드
  Future<void> _loadChatHistory() async {
    isLoading.value = true;
    try {
      final history = await _repository.getChatHistory(issue.id);
      final userId = currentUser.value?.id;
      final updatedHistory = history
          .map(
            (msg) => msg.copyWith(
              isMine: msg.userId == userId,
              deliveryStatus: MessageDeliveryStatus.sent,
            ),
          )
          .toList();

      messages.assignAll(updatedHistory);
      _scrollToBottom();
    } on IssueRepositoryException catch (e) {
      Get.snackbar(
        '오류',
        _repositoryErrorMessage(e),
        snackPosition: SnackPosition.BOTTOM,
      );
    } catch (_) {
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
    await _sendMessageContent(
      textController.text,
      clearInput: true,
      showQueueSnackbar: true,
    );
  }

  /// 실패한 메시지 재시도
  void retryMessage(String messageId) {
    final user = currentUser.value;
    if (user == null) return;

    final index = messages.indexWhere((m) => m.id == messageId);
    if (index == -1) return;

    final target = messages[index];
    if (target.deliveryStatus != MessageDeliveryStatus.failed) {
      return;
    }

    final pending =
        _pendingMessages[messageId] ??
        _PendingMessage(
          clientId: messageId,
          createdAt: target.timestamp,
          userId: target.userId,
          nickname: target.username,
          content: target.content,
        );
    pending.resetForRetry();
    _pendingMessages[messageId] = pending;

    messages[index] = target.copyWith(
      deliveryStatus: MessageDeliveryStatus.pending,
      sendAttempts: pending.attempts,
    );

    _trySendPending(messageId);
    _scheduleReconnect();
  }

  /// 반응 토글
  Future<void> toggleReaction(String messageId) async {
    try {
      final user = currentUser.value;
      if (!isConnected.value || user == null) {
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

      final sent = _realtimeService.toggleReaction(
        issueId: issue.id,
        messageId: messageId,
        userId: user.id,
      );
      if (!sent) {
        messages[index] = message;
        Get.snackbar(
          '전송 실패',
          '반응 요청 전송에 실패했습니다.',
          snackPosition: SnackPosition.BOTTOM,
        );
        _scheduleReconnect();
      }
    } catch (_) {
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
      if (!scrollController.hasClients) return;
      scrollController.animateTo(
        scrollController.position.maxScrollExtent,
        duration: const Duration(milliseconds: 300),
        curve: Curves.easeOut,
      );
    });
  }

  void _connectRealtime() {
    final user = currentUser.value;
    if (user == null) return;

    _realtimeSubscription?.cancel();
    _realtimeSubscription = _realtimeService.events.listen(
      _handleRealtimeEvent,
    );
    _realtimeService.connect(
      issueId: issue.id,
      userId: user.id,
      nickname: user.nickname,
      token: _authToken,
    );
  }

  void _handleRealtimeEvent(Map<String, dynamic> event) {
    final eventIssueId = event['issueId'];
    if (eventIssueId is String &&
        eventIssueId.isNotEmpty &&
        eventIssueId != issue.id) {
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
        _reconnectTimer?.cancel();
        _flushPendingMessages();
        return;
      case ChatEventType.connectionClosed:
      case ChatEventType.connectionError:
        isConnected.value = false;
        isReconnecting.value = true;
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
    final payload = event['message'] ?? event['payload'] ?? event['data'];
    final raw =
        _asMap(payload) ??
        (event.containsKey('content') && event.containsKey('userId')
            ? event
            : null);
    if (raw == null) return;

    final normalized = _normalizeMessagePayload(
      raw,
      fallbackTimestamp: event['serverAt'] ?? event['timestamp'],
    );
    ChatMessage incoming;
    try {
      incoming = ChatMessage.fromJson(normalized).copyWith(
        isMine: normalized['userId'] == currentUser.value?.id,
        deliveryStatus: MessageDeliveryStatus.sent,
      );
    } catch (_) {
      return;
    }

    final clientId =
        _asString(event['clientId']) ?? _asString(normalized['clientId']);
    if (clientId != null) {
      _completePending(clientId);
    }

    _upsertMessage(incoming, clientId: clientId);
  }

  void _handleMessageAck(Map<String, dynamic> event) {
    final clientId = _asString(event['clientId']) ?? _asString(event['tempId']);
    if (clientId == null || clientId.isEmpty) {
      return;
    }

    final serverId =
        _asString(event['serverId']) ??
        _asString(event['messageId']) ??
        _asString(_asMap(event['message'])?['id']);
    final timestamp = _parseTimestamp(
      event['timestamp'] ?? event['sentAt'] ?? event['createdAt'],
    );

    final attempts = _completePending(clientId);
    final index = messages.indexWhere((m) => m.id == clientId);
    if (index == -1) {
      return;
    }

    messages[index] = messages[index].copyWith(
      id: serverId ?? messages[index].id,
      timestamp: timestamp ?? messages[index].timestamp,
      deliveryStatus: MessageDeliveryStatus.sent,
      sendAttempts: attempts ?? messages[index].sendAttempts,
    );
  }

  void _handleReactionUpdate(Map<String, dynamic> event) {
    final messageId = _asString(event['messageId']) ?? _asString(event['id']);
    if (messageId == null) return;

    final index = messages.indexWhere((m) => m.id == messageId);
    if (index == -1) return;

    final count = _asInt(event['count']);
    final isReacted = _asBool(event['isReactedByMe']);

    messages[index] = messages[index].copyWith(
      reactionCount: count ?? messages[index].reactionCount,
      isReactedByMe: isReacted ?? messages[index].isReactedByMe,
    );
  }

  void _upsertMessage(ChatMessage message, {String? clientId}) {
    if (clientId != null) {
      final clientIndex = messages.indexWhere((m) => m.id == clientId);
      if (clientIndex != -1) {
        final previous = messages[clientIndex];
        messages[clientIndex] = message.copyWith(
          isMine: previous.isMine || message.userId == currentUser.value?.id,
          deliveryStatus: MessageDeliveryStatus.sent,
          sendAttempts: previous.sendAttempts,
        );
        return;
      }
    }

    final index = messages.indexWhere((m) => m.id == message.id);
    if (index != -1) {
      final previous = messages[index];
      messages[index] = message.copyWith(
        isMine: previous.isMine || message.userId == currentUser.value?.id,
        deliveryStatus: MessageDeliveryStatus.sent,
        sendAttempts: previous.sendAttempts,
      );
      return;
    }

    messages.add(message.copyWith(deliveryStatus: MessageDeliveryStatus.sent));
    _scrollToBottom();
  }

  Map<String, dynamic> _normalizeMessagePayload(
    Map<String, dynamic> raw, {
    dynamic fallbackTimestamp,
  }) {
    final normalized = Map<String, dynamic>.from(raw);
    final candidate =
        normalized['timestamp'] ??
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
    if (value is DateTime) {
      return value.toIso8601String();
    }
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
    if (value is DateTime) return value;
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
    final message =
        _asString(event['message']) ??
        _asString(event['error']) ??
        '서버 오류가 발생했습니다.';
    Get.snackbar('오류', message, snackPosition: SnackPosition.BOTTOM);
  }

  void _flushPendingMessages() {
    if (_pendingMessages.isEmpty) return;
    for (final clientId in _pendingMessages.keys.toList()) {
      _trySendPending(clientId);
    }
  }

  void _trySendPending(String clientId) {
    final pending = _pendingMessages[clientId];
    final user = currentUser.value;
    if (pending == null || user == null) return;

    if (!isConnected.value) {
      _scheduleReconnect();
      return;
    }

    if (pending.attempts >= _maxSendAttempts) {
      _markMessageFailed(clientId, attempts: pending.attempts);
      _removePending(clientId);
      return;
    }

    pending.attempts += 1;
    _updateMessagePendingState(clientId, attempts: pending.attempts);

    final sent = _realtimeService.sendMessage(
      issueId: issue.id,
      clientId: clientId,
      userId: pending.userId,
      nickname: pending.nickname,
      content: pending.content,
      sentAt: pending.createdAt,
    );

    if (!sent) {
      final delay = _retryDelayForAttempt(pending.attempts);
      _schedulePendingRetry(clientId, delay: delay);
      _scheduleReconnect();
      return;
    }

    _startAckTimer(clientId);
  }

  void _startAckTimer(String clientId) {
    final pending = _pendingMessages[clientId];
    if (pending == null) return;

    pending.timer?.cancel();
    pending.timer = Timer(_ackTimeout, () {
      final stillPending = _pendingMessages[clientId];
      if (stillPending == null) return;
      if (stillPending.attempts >= _maxSendAttempts) {
        _markMessageFailed(clientId, attempts: stillPending.attempts);
        _removePending(clientId);
        return;
      }
      final delay = _retryDelayForAttempt(stillPending.attempts);
      _schedulePendingRetry(clientId, delay: delay);
    });
  }

  void _schedulePendingRetry(String clientId, {required Duration delay}) {
    final pending = _pendingMessages[clientId];
    if (pending == null) return;

    pending.timer?.cancel();
    pending.timer = Timer(delay, () {
      _trySendPending(clientId);
    });
  }

  Duration _retryDelayForAttempt(int attempts) {
    final seconds = min(10, attempts * attempts);
    return Duration(seconds: max(2, seconds));
  }

  int? _completePending(String clientId) {
    final pending = _pendingMessages.remove(clientId);
    if (pending == null) {
      return null;
    }
    final attempts = pending.attempts;
    pending.dispose();
    return attempts;
  }

  void _removePending(String clientId) {
    final pending = _pendingMessages.remove(clientId);
    pending?.dispose();
  }

  void _updateMessagePendingState(String messageId, {required int attempts}) {
    final index = messages.indexWhere((m) => m.id == messageId);
    if (index == -1) return;
    messages[index] = messages[index].copyWith(
      deliveryStatus: MessageDeliveryStatus.pending,
      sendAttempts: attempts,
    );
  }

  void _markMessageFailed(String messageId, {required int attempts}) {
    final index = messages.indexWhere((m) => m.id == messageId);
    if (index == -1) return;
    messages[index] = messages[index].copyWith(
      deliveryStatus: MessageDeliveryStatus.failed,
      sendAttempts: attempts,
    );
    Get.snackbar(
      '전송 실패',
      '메시지 전송에 실패했습니다. 탭해서 다시 시도해주세요.',
      snackPosition: SnackPosition.BOTTOM,
    );
  }

  void _scheduleReconnect() {
    if (!_shouldReconnect) return;
    if (_reconnectTimer?.isActive ?? false) return;

    _reconnectAttempts = min(_reconnectAttempts + 1, _maxReconnectAttempts);
    final seconds = min(30, 1 << (_reconnectAttempts - 1));
    final jitter = _random.nextInt(700);
    final delay = Duration(seconds: seconds, milliseconds: jitter);
    isReconnecting.value = true;

    _reconnectTimer = Timer(delay, () {
      if (!_shouldReconnect) return;
      _connectRealtime();
    });
  }

  String _repositoryErrorMessage(IssueRepositoryException error) {
    if (error.isUnauthorized) {
      return '인증이 만료되었거나 권한이 없습니다.';
    }
    if (error.isTooManyRequests) {
      return '요청이 많습니다. 잠시 후 다시 시도해주세요.';
    }
    if (error.isServerError) {
      return '서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
    }
    return error.message;
  }

  Map<String, dynamic>? _asMap(dynamic value) {
    if (value is Map<String, dynamic>) return value;
    if (value is Map) return Map<String, dynamic>.from(value);
    return null;
  }

  String? _asString(dynamic value) {
    if (value is String) {
      final trimmed = value.trim();
      return trimmed.isEmpty ? null : trimmed;
    }
    if (value is num || value is bool) return value.toString();
    return null;
  }

  int? _asInt(dynamic value) {
    if (value is int) return value;
    if (value is num) return value.toInt();
    if (value is String) return int.tryParse(value);
    return null;
  }

  bool? _asBool(dynamic value) {
    if (value is bool) return value;
    if (value is num) {
      if (value == 1) return true;
      if (value == 0) return false;
    }
    if (value is String) {
      final normalized = value.toLowerCase();
      if (normalized == 'true') return true;
      if (normalized == 'false') return false;
    }
    return null;
  }

  Future<void> _sendMessageContent(
    String rawContent, {
    required bool clearInput,
    required bool showQueueSnackbar,
  }) async {
    final user = currentUser.value;
    final content = rawContent.trim();
    if (content.isEmpty || user == null) return;

    if (content.length > _maxMessageLength) {
      Get.snackbar(
        '입력 제한',
        '메시지는 $_maxMessageLength자 이하로 입력해주세요.',
        snackPosition: SnackPosition.BOTTOM,
      );
      return;
    }

    isSending.value = true;
    final now = DateTime.now();
    final clientId =
        'c_${now.microsecondsSinceEpoch}_${_random.nextInt(999).toString().padLeft(3, '0')}';

    final tempMessage = ChatMessage(
      id: clientId,
      userId: user.id,
      username: user.nickname,
      content: content,
      timestamp: now,
      isMine: true,
      reactionCount: 0,
      isReactedByMe: false,
      deliveryStatus: MessageDeliveryStatus.pending,
      sendAttempts: 0,
    );

    messages.add(tempMessage);
    if (clearInput) {
      textController.clear();
    }
    _scrollToBottom();

    _pendingMessages[clientId] = _PendingMessage(
      clientId: clientId,
      createdAt: now,
      userId: user.id,
      nickname: user.nickname,
      content: content,
    );
    _trySendPending(clientId);

    if (!isConnected.value) {
      if (showQueueSnackbar) {
        Get.snackbar(
          '전송 대기',
          '연결 복구 후 자동 전송됩니다.',
          snackPosition: SnackPosition.BOTTOM,
        );
      }
      _scheduleReconnect();
    }

    isSending.value = false;
  }

  @override
  void onClose() {
    _shouldReconnect = false;
    _reconnectTimer?.cancel();
    _realtimeSubscription?.cancel();
    for (final pending in _pendingMessages.values) {
      pending.dispose();
    }
    _pendingMessages.clear();
    _realtimeService.dispose();
    textController.dispose();
    scrollController.dispose();
    super.onClose();
  }
}

class _PendingMessage {
  _PendingMessage({
    required this.clientId,
    required this.createdAt,
    required this.userId,
    required this.nickname,
    required this.content,
  });

  final String clientId;
  final DateTime createdAt;
  final String userId;
  final String nickname;
  final String content;
  int attempts = 0;
  Timer? timer;

  void resetForRetry() {
    timer?.cancel();
    attempts = 0;
  }

  void dispose() {
    timer?.cancel();
  }
}
