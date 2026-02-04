/// 위키 검색 모드
enum SearchMode {
  semantic,
  keyword,
  hybrid;

  String get value => name;
}

/// 위키 검색 요청
class WikiSearchRequest {
  final String question;
  final int topK;
  final int window;
  final int pageLimit;
  final bool embedMissing;
  final int maxChars;
  final List<int>? pageIds;
  final SearchMode searchMode;

  WikiSearchRequest({
    required this.question,
    this.topK = 5,
    this.window = 3,
    this.pageLimit = 50,
    this.embedMissing = false,
    this.maxChars = 2000,
    this.pageIds,
    this.searchMode = SearchMode.semantic,
  });

  Map<String, dynamic> toJson() {
    return {
      'question': question,
      'top_k': topK,
      'window': window,
      'page_limit': pageLimit,
      'embed_missing': embedMissing,
      'max_chars': maxChars,
      if (pageIds != null) 'page_ids': pageIds,
      'search_mode': searchMode.value,
    };
  }
}

/// 위키 검색 후보
class WikiCandidate {
  final int pageId;
  final String title;
  final int chunkId;
  final String text;
  final double? score;

  WikiCandidate({
    required this.pageId,
    required this.title,
    required this.chunkId,
    required this.text,
    this.score,
  });

  factory WikiCandidate.fromJson(Map<String, dynamic> json) {
    return WikiCandidate(
      pageId: json['page_id'] as int,
      title: json['title'] as String,
      chunkId: json['chunk_id'] as int,
      text: json['text'] as String,
      score: (json['score'] as num?)?.toDouble(),
    );
  }
}

/// 위키 검색 히트
class WikiHit {
  final int pageId;
  final String title;
  final String url;
  final String context;

  WikiHit({
    required this.pageId,
    required this.title,
    required this.url,
    required this.context,
  });

  factory WikiHit.fromJson(Map<String, dynamic> json) {
    return WikiHit(
      pageId: json['page_id'] as int,
      title: json['title'] as String,
      url: json['url'] as String,
      context: json['context'] as String,
    );
  }
}

/// 위키 검색 응답
class WikiSearchResponse {
  final String question;
  final List<WikiCandidate> candidates;
  final List<WikiHit> hits;
  final int? updatedEmbeddings;
  final Map<String, dynamic>? debug;
  final String? promptContext;

  WikiSearchResponse({
    required this.question,
    required this.candidates,
    required this.hits,
    this.updatedEmbeddings,
    this.debug,
    this.promptContext,
  });

  factory WikiSearchResponse.fromJson(Map<String, dynamic> json) {
    return WikiSearchResponse(
      question: json['question'] as String,
      candidates: (json['candidates'] as List?)
              ?.map((e) => WikiCandidate.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      hits: (json['hits'] as List?)
              ?.map((e) => WikiHit.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
      updatedEmbeddings: json['updated_embeddings'] as int?,
      debug: json['debug'] as Map<String, dynamic>?,
      promptContext: json['prompt_context'] as String?,
    );
  }
}

/// 키워드 검색 요청
class KeywordSearchRequest {
  final String query;
  final int limit;

  KeywordSearchRequest({
    required this.query,
    this.limit = 12,
  });

  Map<String, dynamic> toJson() {
    return {
      'query': query,
      'limit': limit,
    };
  }
}

/// 키워드 검색 히트
class KeywordHit {
  final int pageId;
  final String title;

  KeywordHit({
    required this.pageId,
    required this.title,
  });

  factory KeywordHit.fromJson(Map<String, dynamic> json) {
    return KeywordHit(
      pageId: json['page_id'] as int,
      title: json['title'] as String,
    );
  }
}

/// 키워드 검색 응답
class KeywordSearchResponse {
  final String query;
  final List<KeywordHit> hits;

  KeywordSearchResponse({
    required this.query,
    required this.hits,
  });

  factory KeywordSearchResponse.fromJson(Map<String, dynamic> json) {
    return KeywordSearchResponse(
      query: json['query'] as String,
      hits: (json['hits'] as List?)
              ?.map((e) => KeywordHit.fromJson(e as Map<String, dynamic>))
              .toList() ??
          [],
    );
  }
}
