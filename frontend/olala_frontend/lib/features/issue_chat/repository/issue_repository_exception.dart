class IssueRepositoryException implements Exception {
  final String message;
  final int? statusCode;
  final Object? cause;

  const IssueRepositoryException(this.message, {this.statusCode, this.cause});

  bool get isUnauthorized => statusCode == 401 || statusCode == 403;
  bool get isNotFound => statusCode == 404;
  bool get isTooManyRequests => statusCode == 429;
  bool get isServerError => statusCode != null && statusCode! >= 500;

  @override
  String toString() {
    final codeText = statusCode == null ? '' : ' (status: $statusCode)';
    final causeText = cause == null ? '' : ' | cause: $cause';
    return 'IssueRepositoryException: $message$codeText$causeText';
  }
}
