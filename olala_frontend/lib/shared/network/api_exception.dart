import 'package:dio/dio.dart';

/// API 호출 시 발생할 수 있는 예외를 정의합니다.
class ApiException implements Exception {
  final String message;
  final int? statusCode;
  final dynamic data;
  final ApiExceptionType type;

  ApiException({
    required this.message,
    this.statusCode,
    this.data,
    this.type = ApiExceptionType.unknown,
  });

  /// DioException을 ApiException으로 변환
  factory ApiException.fromDioException(DioException error) {
    switch (error.type) {
      case DioExceptionType.connectionTimeout:
      case DioExceptionType.sendTimeout:
      case DioExceptionType.receiveTimeout:
        return ApiException(
          message: '서버 응답 시간이 초과되었습니다.',
          type: ApiExceptionType.timeout,
        );

      case DioExceptionType.badResponse:
        return _handleBadResponse(error.response);

      case DioExceptionType.cancel:
        return ApiException(
          message: '요청이 취소되었습니다.',
          type: ApiExceptionType.cancel,
        );

      case DioExceptionType.connectionError:
        return ApiException(
          message: '인터넷 연결을 확인해주세요.',
          type: ApiExceptionType.networkError,
        );

      case DioExceptionType.badCertificate:
        return ApiException(
          message: '인증서 오류가 발생했습니다.',
          type: ApiExceptionType.unknown,
        );

      case DioExceptionType.unknown:
        return ApiException(
          message: '알 수 없는 오류가 발생했습니다.',
          type: ApiExceptionType.unknown,
        );
    }
  }

  /// HTTP 상태 코드에 따른 예외 처리
  static ApiException _handleBadResponse(Response? response) {
    final statusCode = response?.statusCode;
    final data = response?.data;

    String message = '서버 오류가 발생했습니다.';
    ApiExceptionType type = ApiExceptionType.serverError;

    if (statusCode != null) {
      switch (statusCode) {
        case 400:
          message = '잘못된 요청입니다.';
          type = ApiExceptionType.badRequest;
          // 서버에서 보낸 에러 메시지가 있으면 사용
          if (data is Map && data['detail'] != null) {
            message = data['detail'].toString();
          }
          break;
        case 401:
          message = '인증이 필요합니다.';
          type = ApiExceptionType.unauthorized;
          break;
        case 403:
          message = '접근 권한이 없습니다.';
          type = ApiExceptionType.forbidden;
          break;
        case 404:
          message = '요청한 리소스를 찾을 수 없습니다.';
          type = ApiExceptionType.notFound;
          break;
        case 422:
          message = '입력 데이터가 유효하지 않습니다.';
          type = ApiExceptionType.validationError;
          // FastAPI 검증 에러 메시지 파싱
          if (data is Map && data['detail'] != null) {
            if (data['detail'] is List) {
              final errors = (data['detail'] as List)
                  .map((e) => e['msg'] ?? e.toString())
                  .join('\n');
              message = errors;
            } else {
              message = data['detail'].toString();
            }
          }
          break;
        case 429:
          message = '너무 많은 요청을 보냈습니다. 잠시 후 다시 시도해주세요.';
          type = ApiExceptionType.tooManyRequests;
          break;
        case 500:
        case 502:
        case 503:
        case 504:
          message = '서버 오류가 발생했습니다. 잠시 후 다시 시도해주세요.';
          type = ApiExceptionType.serverError;
          break;
        default:
          message = '오류가 발생했습니다. (코드: $statusCode)';
          type = ApiExceptionType.unknown;
      }
    }

    return ApiException(
      message: message,
      statusCode: statusCode,
      data: data,
      type: type,
    );
  }

  @override
  String toString() {
    return 'ApiException{message: $message, statusCode: $statusCode, type: $type}';
  }
}

/// API 예외 타입
enum ApiExceptionType {
  /// 네트워크 연결 오류
  networkError,

  /// 타임아웃
  timeout,

  /// 요청 취소
  cancel,

  /// 잘못된 요청 (400)
  badRequest,

  /// 인증 필요 (401)
  unauthorized,

  /// 접근 금지 (403)
  forbidden,

  /// 찾을 수 없음 (404)
  notFound,

  /// 검증 오류 (422)
  validationError,

  /// 너무 많은 요청 (429)
  tooManyRequests,

  /// 서버 오류 (5xx)
  serverError,

  /// 알 수 없는 오류
  unknown,
}
