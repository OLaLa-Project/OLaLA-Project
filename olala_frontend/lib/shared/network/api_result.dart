import 'api_exception.dart';

/// API 호출 결과를 Success 또는 Failure로 래핑하는 Result 패턴
///
/// 사용 예시:
/// ```dart
/// final result = await apiClient.get<User>('/user/1');
/// result.when(
///   success: (user) => print('User: ${user.name}'),
///   failure: (error) => print('Error: ${error.message}'),
/// );
/// ```
sealed class ApiResult<T> {
  const ApiResult();

  /// 성공 케이스
  bool get isSuccess => this is Success<T>;

  /// 실패 케이스
  bool get isFailure => this is Failure<T>;

  /// 성공 시 데이터 반환, 실패 시 null
  T? get dataOrNull => isSuccess ? (this as Success<T>).data : null;

  /// 실패 시 에러 반환, 성공 시 null
  ApiException? get errorOrNull =>
      isFailure ? (this as Failure<T>).error : null;

  /// Result 패턴 매칭
  R when<R>({
    required R Function(T data) success,
    required R Function(ApiException error) failure,
  }) {
    if (this is Success<T>) {
      return success((this as Success<T>).data);
    } else {
      return failure((this as Failure<T>).error);
    }
  }

  /// Result 패턴 매칭 (비동기)
  Future<R> whenAsync<R>({
    required Future<R> Function(T data) success,
    required Future<R> Function(ApiException error) failure,
  }) async {
    if (this is Success<T>) {
      return await success((this as Success<T>).data);
    } else {
      return await failure((this as Failure<T>).error);
    }
  }

  /// 성공 시에만 실행
  void onSuccess(void Function(T data) action) {
    if (this is Success<T>) {
      action((this as Success<T>).data);
    }
  }

  /// 실패 시에만 실행
  void onFailure(void Function(ApiException error) action) {
    if (this is Failure<T>) {
      action((this as Failure<T>).error);
    }
  }

  /// 데이터 변환 (map)
  ApiResult<R> map<R>(R Function(T data) transform) {
    if (this is Success<T>) {
      try {
        return Success(transform((this as Success<T>).data));
      } catch (e) {
        return Failure(ApiException(
          message: '데이터 변환 중 오류가 발생했습니다: $e',
          type: ApiExceptionType.unknown,
        ));
      }
    } else {
      return Failure((this as Failure<T>).error);
    }
  }

  /// 비동기 데이터 변환 (flatMap)
  Future<ApiResult<R>> flatMap<R>(
      Future<ApiResult<R>> Function(T data) transform) async {
    if (this is Success<T>) {
      try {
        return await transform((this as Success<T>).data);
      } catch (e) {
        return Failure(ApiException(
          message: '데이터 변환 중 오류가 발생했습니다: $e',
          type: ApiExceptionType.unknown,
        ));
      }
    } else {
      return Failure((this as Failure<T>).error);
    }
  }
}

/// 성공 케이스
class Success<T> extends ApiResult<T> {
  final T data;

  const Success(this.data);

  @override
  String toString() => 'Success(data: $data)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Success<T> &&
          runtimeType == other.runtimeType &&
          data == other.data;

  @override
  int get hashCode => data.hashCode;
}

/// 실패 케이스
class Failure<T> extends ApiResult<T> {
  final ApiException error;

  const Failure(this.error);

  @override
  String toString() => 'Failure(error: $error)';

  @override
  bool operator ==(Object other) =>
      identical(this, other) ||
      other is Failure<T> &&
          runtimeType == other.runtimeType &&
          error == other.error;

  @override
  int get hashCode => error.hashCode;
}
