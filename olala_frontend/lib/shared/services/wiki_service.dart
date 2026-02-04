import '../models/wiki_model.dart';
import '../network/api_client.dart';
import '../network/api_result.dart';

/// 위키 API 서비스
class WikiService {
  final ApiClient _client;

  WikiService({ApiClient? client}) : _client = client ?? ApiClient.instance;

  /// 위키 시맨틱 검색
  ///
  /// [request] 위키 검색 요청 데이터
  ///
  /// Returns: [ApiResult<WikiSearchResponse>]
  Future<ApiResult<WikiSearchResponse>> search(
    WikiSearchRequest request,
  ) async {
    return await _client.post<WikiSearchResponse>(
      '/api/wiki/search',
      data: request.toJson(),
      parser: (data) =>
          WikiSearchResponse.fromJson(data as Map<String, dynamic>),
    );
  }

  /// 위키 키워드 검색
  ///
  /// [request] 키워드 검색 요청 데이터
  ///
  /// Returns: [ApiResult<KeywordSearchResponse>]
  Future<ApiResult<KeywordSearchResponse>> keywordSearch(
    KeywordSearchRequest request,
  ) async {
    return await _client.post<KeywordSearchResponse>(
      '/api/wiki/keyword-search',
      data: request.toJson(),
      parser: (data) =>
          KeywordSearchResponse.fromJson(data as Map<String, dynamic>),
    );
  }
}
