class ChatJoinLink {
  static const String webChatPath = 'web-chat';

  const ChatJoinLink._();

  static Uri? parseBaseHttpUrl(String rawUrl) {
    final input = rawUrl.trim();
    if (input.isEmpty) return null;

    final uri = Uri.tryParse(input);
    if (uri == null || uri.host.isEmpty) return null;
    if (uri.scheme != 'http' && uri.scheme != 'https') return null;

    return uri;
  }

  static bool isPublicWebBaseUrl(Uri baseUrl) {
    if ((baseUrl.scheme != 'http' && baseUrl.scheme != 'https') ||
        baseUrl.host.isEmpty) {
      return false;
    }
    return !_isLocalOrPrivateHost(baseUrl.host);
  }

  static String buildWebChatLink({
    required Uri baseUrl,
    required String issueId,
    String? title,
  }) {
    final normalizedPath = _normalizedBasePath(baseUrl.path);
    final chatPathValue = normalizedPath.isEmpty
        ? '/$webChatPath'
        : '$normalizedPath/$webChatPath';

    return baseUrl
        .replace(
          path: chatPathValue,
          queryParameters: _buildQuery(issueId: issueId, title: title),
          fragment: '',
        )
        .toString();
  }

  // Backward-compatible alias for older call sites.
  static String buildWebJoinLink({
    required Uri baseUrl,
    required String issueId,
    String? title,
  }) {
    return buildWebChatLink(baseUrl: baseUrl, issueId: issueId, title: title);
  }

  static String? extractIssueId(String rawLink) {
    final input = rawLink.trim();
    if (input.isEmpty) return null;

    final uri = Uri.tryParse(input);
    if (uri == null) return null;

    if (!_isWebChatUri(uri)) return null;

    final issueId = uri.queryParameters['issueId']?.trim();
    if (issueId == null || issueId.isEmpty) return null;
    return issueId;
  }

  static bool _isWebChatUri(Uri uri) {
    if ((uri.scheme != 'http' && uri.scheme != 'https') || uri.host.isEmpty) {
      return false;
    }

    return uri.pathSegments.isNotEmpty && uri.pathSegments.last == webChatPath;
  }

  static String _normalizedBasePath(String path) {
    if (path.isEmpty || path == '/') return '';
    final withoutTrailingSlash = path.endsWith('/')
        ? path.substring(0, path.length - 1)
        : path;
    return withoutTrailingSlash.startsWith('/')
        ? withoutTrailingSlash
        : '/$withoutTrailingSlash';
  }

  static bool _isLocalOrPrivateHost(String host) {
    final normalizedHost = host.trim().toLowerCase();
    if (normalizedHost.isEmpty) return true;

    if (normalizedHost == 'localhost' ||
        normalizedHost == '127.0.0.1' ||
        normalizedHost == '0.0.0.0' ||
        normalizedHost == '::1' ||
        normalizedHost.endsWith('.local')) {
      return true;
    }

    final ipv4Match = RegExp(
      r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$',
    ).firstMatch(normalizedHost);
    if (ipv4Match == null) {
      return false;
    }

    final octets = List<int>.generate(
      4,
      (index) => int.tryParse(ipv4Match.group(index + 1) ?? '') ?? -1,
    );
    if (octets.any((value) => value < 0 || value > 255)) {
      return true;
    }

    final first = octets[0];
    final second = octets[1];
    if (first == 10) return true;
    if (first == 127) return true;
    if (first == 192 && second == 168) return true;
    if (first == 172 && second >= 16 && second <= 31) return true;
    return false;
  }

  static Map<String, String> _buildQuery({
    required String issueId,
    String? title,
  }) {
    final query = <String, String>{'issueId': issueId};
    final trimmedTitle = title?.trim();
    if (trimmedTitle != null && trimmedTitle.isNotEmpty) {
      query['title'] = trimmedTitle;
    }
    return query;
  }
}
