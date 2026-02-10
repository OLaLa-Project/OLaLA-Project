import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:qr_flutter/qr_flutter.dart';

import '../../../shared/network/api_endpoints.dart';
import '../../../shared/storage/local_storage.dart';
import '../models/daily_issue.dart';
import '../services/chat_join_link.dart';

class QrCodeDialog extends StatefulWidget {
  final DailyIssue issue;

  const QrCodeDialog({super.key, required this.issue});

  static void show(BuildContext context, DailyIssue issue) {
    showDialog(
      context: context,
      builder: (_) => QrCodeDialog(issue: issue),
    );
  }

  @override
  State<QrCodeDialog> createState() => _QrCodeDialogState();
}

class _QrCodeDialogState extends State<QrCodeDialog> {
  final TextEditingController _publicUrlCtrl = TextEditingController();
  bool _isInitializing = true;

  @override
  void initState() {
    super.initState();
    unawaited(_initPublicBaseUrl());
  }

  @override
  void dispose() {
    _publicUrlCtrl.dispose();
    super.dispose();
  }

  bool get _hasPublicUrlInput => _publicUrlCtrl.text.trim().isNotEmpty;

  Uri? get _parsedPublicBaseUrl =>
      ChatJoinLink.parseBaseHttpUrl(_publicUrlCtrl.text);

  bool get _isValidPublicBaseUrl {
    final parsed = _parsedPublicBaseUrl;
    return parsed != null && ChatJoinLink.isPublicWebBaseUrl(parsed);
  }

  String? get _publicUrlErrorText {
    if (!_hasPublicUrlInput) return null;

    final parsed = _parsedPublicBaseUrl;
    if (parsed == null) {
      return 'http/https 형식의 유효한 URL을 입력해주세요.';
    }
    if (!ChatJoinLink.isPublicWebBaseUrl(parsed)) {
      return '로컬 주소는 사용할 수 없습니다. 공개 URL(ngrok 등)을 입력해주세요.';
    }
    return null;
  }

  String? get _joinUrl {
    final parsedBase = _parsedPublicBaseUrl;
    if (parsedBase == null || !ChatJoinLink.isPublicWebBaseUrl(parsedBase)) {
      return null;
    }
    return ChatJoinLink.buildWebChatLink(
      baseUrl: parsedBase,
      issueId: widget.issue.id,
      title: widget.issue.title,
    );
  }

  Future<void> _initPublicBaseUrl() async {
    final saved = await LocalStorage.getAudienceWebBaseUrl();
    var seed = saved;
    seed ??= _defaultPublicWebBaseFromDefine();
    seed ??= _defaultPublicWebBaseFromApiBase();

    if (!mounted) return;
    if (seed != null && seed.isNotEmpty) {
      _publicUrlCtrl.text = seed;
    }
    setState(() => _isInitializing = false);
  }

  String? _defaultPublicWebBaseFromDefine() {
    final parsed = ChatJoinLink.parseBaseHttpUrl(ApiEndpoints.publicWebBase);
    if (parsed == null || !ChatJoinLink.isPublicWebBaseUrl(parsed)) {
      return null;
    }
    return parsed.toString();
  }

  String? _defaultPublicWebBaseFromApiBase() {
    final apiUri = ChatJoinLink.parseBaseHttpUrl(ApiEndpoints.apiBase);
    if (apiUri == null) return null;

    final segments = List<String>.from(apiUri.pathSegments);
    if (segments.isNotEmpty && segments.last.toLowerCase() == 'v1') {
      segments.removeLast();
    }

    final normalizedPath = segments.isEmpty ? '' : '/${segments.join('/')}';
    final baseUri = apiUri.replace(
      path: normalizedPath,
      query: null,
      fragment: null,
    );
    if (!ChatJoinLink.isPublicWebBaseUrl(baseUri)) {
      return null;
    }
    return baseUri.toString();
  }

  Future<void> _onPublicUrlChanged(String value) async {
    setState(() {});
    final parsed = _parsedPublicBaseUrl;
    if (parsed != null && ChatJoinLink.isPublicWebBaseUrl(parsed)) {
      await LocalStorage.setAudienceWebBaseUrl(parsed.toString());
    }
  }

  Future<void> _pastePublicUrl() async {
    final data = await Clipboard.getData('text/plain');
    if (data?.text == null) return;
    _publicUrlCtrl.text = data!.text!.trim();
    await _onPublicUrlChanged(_publicUrlCtrl.text);
  }

  Future<void> _copyLink(BuildContext context, String? text) async {
    if (text == null || text.trim().isEmpty) {
      ScaffoldMessenger.of(context).showSnackBar(
        const SnackBar(
          content: Text('공개 URL을 먼저 입력해주세요'),
          duration: Duration(seconds: 2),
        ),
      );
      return;
    }

    await Clipboard.setData(ClipboardData(text: text));
    if (!context.mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('링크를 복사했어요'),
        duration: Duration(seconds: 2),
      ),
    );
  }

  Widget _buildQrArea({
    required ThemeData theme,
    required bool isDark,
    required String? joinUrl,
  }) {
    if (joinUrl == null) {
      return SizedBox(
        width: 220,
        height: 220,
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            Icon(
              Icons.qr_code_2_outlined,
              size: 52,
              color: isDark ? theme.colorScheme.outline : Colors.grey[500],
            ),
            const SizedBox(height: 12),
            Text(
              '공개 URL을 입력하면\nQR 코드가 생성됩니다',
              textAlign: TextAlign.center,
              style: TextStyle(
                fontSize: 13,
                color: isDark
                    ? theme.colorScheme.onSurfaceVariant
                    : Colors.grey[600],
                height: 1.4,
              ),
            ),
          ],
        ),
      );
    }

    return QrImageView(
      data: joinUrl,
      version: QrVersions.auto,
      size: 220,
      backgroundColor: Colors.white,
    );
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final joinUrl = _joinUrl;

    return Dialog(
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      backgroundColor: isDark ? theme.colorScheme.surface : Colors.white,
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Text(
              '사용자 참여 QR 코드',
              style: TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w700,
                color: isDark ? theme.colorScheme.onSurface : Colors.black,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              widget.issue.title,
              textAlign: TextAlign.center,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: TextStyle(
                fontSize: 14,
                color: isDark
                    ? theme.colorScheme.onSurfaceVariant
                    : Colors.grey[600],
              ),
            ),
            const SizedBox(height: 16),
            TextField(
              controller: _publicUrlCtrl,
              onChanged: _onPublicUrlChanged,
              keyboardType: TextInputType.url,
              textInputAction: TextInputAction.done,
              autocorrect: false,
              enableSuggestions: false,
              enabled: !_isInitializing,
              decoration: InputDecoration(
                labelText: '공개 웹 URL (필수)',
                hintText: 'https://abcd-1234.ngrok-free.app',
                helperText: '사용자 휴대폰에서 앱 설치 없이 참여하려면 공개 URL이 필요합니다.',
                helperMaxLines: 2,
                errorText: _publicUrlErrorText,
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12),
                ),
                suffixIcon: IconButton(
                  icon: const Icon(Icons.content_paste),
                  onPressed: _isInitializing ? null : _pastePublicUrl,
                  tooltip: '붙여넣기',
                ),
              ),
            ),
            if (!_hasPublicUrlInput) ...[
              const SizedBox(height: 6),
              Align(
                alignment: Alignment.centerLeft,
                child: Text(
                  '예: ngrok/Cloudflare Tunnel URL',
                  style: TextStyle(
                    fontSize: 11,
                    color: isDark
                        ? theme.colorScheme.onSurfaceVariant
                        : Colors.grey[600],
                  ),
                ),
              ),
            ],
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(12),
                boxShadow: isDark
                    ? []
                    : [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.08),
                          blurRadius: 8,
                          offset: const Offset(0, 2),
                        ),
                      ],
              ),
              child: _buildQrArea(
                theme: theme,
                isDark: isDark,
                joinUrl: joinUrl,
              ),
            ),
            const SizedBox(height: 12),
            GestureDetector(
              onLongPress: () => _copyLink(context, joinUrl),
              child: Container(
                width: double.infinity,
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 10,
                ),
                decoration: BoxDecoration(
                  color: isDark
                      ? theme.colorScheme.surfaceContainerHighest
                      : const Color(0xFFF7F7F7),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Text(
                  joinUrl ?? '링크가 아직 준비되지 않았습니다',
                  maxLines: 2,
                  overflow: TextOverflow.ellipsis,
                  textAlign: TextAlign.center,
                  style: TextStyle(
                    fontSize: 11,
                    color: isDark
                        ? theme.colorScheme.onSurfaceVariant
                        : Colors.grey[700],
                  ),
                ),
              ),
            ),
            const SizedBox(height: 4),
            Text(
              '길게 눌러서 복사',
              style: TextStyle(
                fontSize: 10,
                color: isDark
                    ? theme.colorScheme.onSurfaceVariant
                    : Colors.grey[500],
              ),
            ),
            const SizedBox(height: 16),
            Row(
              children: [
                Expanded(
                  child: OutlinedButton(
                    onPressed: _isValidPublicBaseUrl
                        ? () => _copyLink(context, joinUrl)
                        : null,
                    style: OutlinedButton.styleFrom(
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: const Text('링크 복사'),
                  ),
                ),
                const SizedBox(width: 10),
                Expanded(
                  child: ElevatedButton(
                    onPressed: () => Navigator.of(context).pop(),
                    style: ElevatedButton.styleFrom(
                      backgroundColor: const Color(0xFF4683F6),
                      foregroundColor: Colors.white,
                      elevation: 0,
                      padding: const EdgeInsets.symmetric(vertical: 14),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    child: const Text(
                      '닫기',
                      style: TextStyle(fontWeight: FontWeight.w600),
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
