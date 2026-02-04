import 'package:dio/dio.dart';
import 'package:pretty_dio_logger/pretty_dio_logger.dart';

import '../../app/env.dart';
import 'api_exception.dart';
import 'api_result.dart';

/// API 통신을 담당하는 클라이언트 (Singleton)
///
/// 사용 예시:
/// ```dart
/// final client = ApiClient.instance;
/// final result = await client.get<Map<String, dynamic>>('/health');
/// ```
class ApiClient {
  static final ApiClient _instance = ApiClient._internal();
  static ApiClient get instance => _instance;

  late final Dio _dio;

  ApiClient._internal() {
    _dio = Dio(_createBaseOptions());
    _setupInterceptors();
  }

  /// Dio 인스턴스 (테스트/특수 상황용)
  Dio get dio => _dio;

  /// 기본 옵션 설정
  BaseOptions _createBaseOptions() {
    return BaseOptions(
      baseUrl: Env.apiBaseUrl,
      connectTimeout: Duration(seconds: Env.connectTimeout),
      receiveTimeout: Duration(seconds: Env.receiveTimeout),
      sendTimeout: Duration(seconds: Env.sendTimeout),
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      validateStatus: (status) {
        // 2xx, 3xx는 성공으로 처리
        return status != null && status < 400;
      },
    );
  }

  /// 인터셉터 설정
  void _setupInterceptors() {
    // 로깅 인터셉터 (개발 환경에서만)
    if (Env.enableApiLog) {
      _dio.interceptors.add(
        PrettyDioLogger(
          requestHeader: true,
          requestBody: true,
          responseBody: true,
          responseHeader: false,
          error: true,
          compact: true,
          maxWidth: 90,
        ),
      );
    }

    // 커스텀 인터셉터 (인증 토큰, 공통 헤더 등)
    _dio.interceptors.add(
      InterceptorsWrapper(
        onRequest: (options, handler) async {
          // TODO: 필요시 인증 토큰 추가
          // final token = await getAuthToken();
          // if (token != null) {
          //   options.headers['Authorization'] = 'Bearer $token';
          // }

          return handler.next(options);
        },
        onError: (error, handler) async {
          // TODO: 필요시 토큰 갱신 로직
          // if (error.response?.statusCode == 401) {
          //   // 토큰 갱신 시도
          // }

          return handler.next(error);
        },
      ),
    );
  }

  /// GET 요청
  Future<ApiResult<T>> get<T>(
    String path, {
    Map<String, dynamic>? queryParameters,
    Options? options,
    CancelToken? cancelToken,
    T Function(dynamic)? parser,
  }) async {
    try {
      final response = await _dio.get(
        path,
        queryParameters: queryParameters,
        options: options,
        cancelToken: cancelToken,
      );

      final data = parser != null ? parser(response.data) : response.data as T;
      return Success(data);
    } on DioException catch (e) {
      return Failure(ApiException.fromDioException(e));
    } catch (e) {
      return Failure(ApiException(
        message: '예상치 못한 오류가 발생했습니다: $e',
        type: ApiExceptionType.unknown,
      ));
    }
  }

  /// POST 요청
  Future<ApiResult<T>> post<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
    CancelToken? cancelToken,
    T Function(dynamic)? parser,
  }) async {
    try {
      final response = await _dio.post(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
        cancelToken: cancelToken,
      );

      final result =
          parser != null ? parser(response.data) : response.data as T;
      return Success(result);
    } on DioException catch (e) {
      return Failure(ApiException.fromDioException(e));
    } catch (e) {
      return Failure(ApiException(
        message: '예상치 못한 오류가 발생했습니다: $e',
        type: ApiExceptionType.unknown,
      ));
    }
  }

  /// PUT 요청
  Future<ApiResult<T>> put<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
    CancelToken? cancelToken,
    T Function(dynamic)? parser,
  }) async {
    try {
      final response = await _dio.put(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
        cancelToken: cancelToken,
      );

      final result =
          parser != null ? parser(response.data) : response.data as T;
      return Success(result);
    } on DioException catch (e) {
      return Failure(ApiException.fromDioException(e));
    } catch (e) {
      return Failure(ApiException(
        message: '예상치 못한 오류가 발생했습니다: $e',
        type: ApiExceptionType.unknown,
      ));
    }
  }

  /// PATCH 요청
  Future<ApiResult<T>> patch<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
    CancelToken? cancelToken,
    T Function(dynamic)? parser,
  }) async {
    try {
      final response = await _dio.patch(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
        cancelToken: cancelToken,
      );

      final result =
          parser != null ? parser(response.data) : response.data as T;
      return Success(result);
    } on DioException catch (e) {
      return Failure(ApiException.fromDioException(e));
    } catch (e) {
      return Failure(ApiException(
        message: '예상치 못한 오류가 발생했습니다: $e',
        type: ApiExceptionType.unknown,
      ));
    }
  }

  /// DELETE 요청
  Future<ApiResult<T>> delete<T>(
    String path, {
    dynamic data,
    Map<String, dynamic>? queryParameters,
    Options? options,
    CancelToken? cancelToken,
    T Function(dynamic)? parser,
  }) async {
    try {
      final response = await _dio.delete(
        path,
        data: data,
        queryParameters: queryParameters,
        options: options,
        cancelToken: cancelToken,
      );

      final result =
          parser != null ? parser(response.data) : response.data as T;
      return Success(result);
    } on DioException catch (e) {
      return Failure(ApiException.fromDioException(e));
    } catch (e) {
      return Failure(ApiException(
        message: '예상치 못한 오류가 발생했습니다: $e',
        type: ApiExceptionType.unknown,
      ));
    }
  }

  /// 파일 업로드
  Future<ApiResult<T>> uploadFile<T>(
    String path, {
    required String filePath,
    required String fileKey,
    Map<String, dynamic>? data,
    ProgressCallback? onSendProgress,
    T Function(dynamic)? parser,
  }) async {
    try {
      final formData = FormData.fromMap({
        ...?data,
        fileKey: await MultipartFile.fromFile(filePath),
      });

      final response = await _dio.post(
        path,
        data: formData,
        onSendProgress: onSendProgress,
      );

      final result =
          parser != null ? parser(response.data) : response.data as T;
      return Success(result);
    } on DioException catch (e) {
      return Failure(ApiException.fromDioException(e));
    } catch (e) {
      return Failure(ApiException(
        message: '파일 업로드 중 오류가 발생했습니다: $e',
        type: ApiExceptionType.unknown,
      ));
    }
  }

  /// 파일 다운로드
  Future<ApiResult<void>> downloadFile(
    String path,
    String savePath, {
    Map<String, dynamic>? queryParameters,
    ProgressCallback? onReceiveProgress,
    CancelToken? cancelToken,
  }) async {
    try {
      await _dio.download(
        path,
        savePath,
        queryParameters: queryParameters,
        onReceiveProgress: onReceiveProgress,
        cancelToken: cancelToken,
      );

      return const Success(null);
    } on DioException catch (e) {
      return Failure(ApiException.fromDioException(e));
    } catch (e) {
      return Failure(ApiException(
        message: '파일 다운로드 중 오류가 발생했습니다: $e',
        type: ApiExceptionType.unknown,
      ));
    }
  }
}
