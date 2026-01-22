import 'package:flutter/material.dart';
import '../services/api_service.dart';
import '../models/verification_result.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final TextEditingController _controller = TextEditingController();
  bool _isLoading = false;
  VerificationResult? _result;
  String? _error;

  Future<void> _checkClaim() async {
    setState(() {
      _isLoading = true;
      _error = null;
      _result = null;
    });

    try {
      final api = ApiService();
      final res = await api.verifyClaim(_controller.text.trim());
      setState(() {
        _result = res;
      });
    } catch (e) {
      setState(() {
        _error = e.toString();
      });
    }

    setState(() {
      _isLoading = false;
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('OLaLA'),
        centerTitle: true,
      ),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          children: [
            TextField(
              controller: _controller,
              maxLines: 4,
              decoration: const InputDecoration(
                hintText: '검증할 뉴스나 주장을 입력하세요...',
                border: OutlineInputBorder(),
              ),
            ),
            const SizedBox(height: 16),
            ElevatedButton(
              onPressed: _isLoading ? null : _checkClaim,
              child: _isLoading
                  ? const CircularProgressIndicator()
                  : const Text('검증하기'),
            ),
            const SizedBox(height: 24),
            if (_error != null) Text('오류: $_error'),
            if (_result != null) ...[
              Text('라벨: ${_result!.label}'),
              Text('요약: ${_result!.summary}'),
            ],
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }
}
