import 'dart:convert';
import 'package:http/http.dart' as http;
import '../models/verification_result.dart';

class ApiService {
  // TODO: 실제 서버 URL로 변경
  static const String baseUrl = 'http://localhost:8000';

  /// 주장을 검증하는 API 호출
  Future<VerificationResult> verifyClaim(String claim) async {
    final response = await http.post(
      Uri.parse('$baseUrl/truth/check'),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'input_type': 'text',
        'input_payload': claim,
        'user_request': '이 내용이 사실인지 확인해줘',
      }),
    );

    if (response.statusCode == 200) {
      return VerificationResult.fromJson(jsonDecode(response.body));
    } else {
      throw Exception('검증 요청 실패: ${response.statusCode}');
    }
  }
}
