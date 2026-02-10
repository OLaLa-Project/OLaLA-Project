import 'package:flutter/material.dart';
import 'package:mobile_scanner/mobile_scanner.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../services/chat_join_link.dart';

/// QR 코드 스캔 화면
class QrScannerScreen extends StatefulWidget {
  const QrScannerScreen({super.key});

  @override
  State<QrScannerScreen> createState() => _QrScannerScreenState();
}

class _QrScannerScreenState extends State<QrScannerScreen> {
  static const Duration _retryDelay = Duration(seconds: 2);

  final MobileScannerController _controller = MobileScannerController(
    detectionSpeed: DetectionSpeed.normal,
    facing: CameraFacing.back,
  );

  bool _isProcessing = false;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  void _onDetect(BarcodeCapture capture) {
    if (_isProcessing) return;

    final code = capture.barcodes
        .map((barcode) => barcode.rawValue?.trim())
        .whereType<String>()
        .firstWhere((value) => value.isNotEmpty, orElse: () => '');
    if (code.isEmpty) return;

    if (ChatJoinLink.extractIssueId(code) == null) {
      _showError('지원하지 않는 QR 코드입니다.');
      return;
    }

    setState(() => _isProcessing = true);
    Navigator.of(context).pop(code); // 스캔 결과 반환
  }

  void _showError(String message) {
    setState(() => _isProcessing = true);
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text(message),
        backgroundColor: Colors.red,
        duration: _retryDelay,
      ),
    );
    // 잠시 후 다시 스캔 가능하도록
    Future.delayed(_retryDelay, () {
      if (mounted) {
        setState(() => _isProcessing = false);
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.black,
      appBar: AppBar(
        backgroundColor: Colors.black,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(PhosphorIconsRegular.x, color: Colors.white),
          onPressed: () => Navigator.of(context).pop(),
        ),
        title: const Text(
          'QR 코드 스캔',
          style: TextStyle(color: Colors.white, fontWeight: FontWeight.w600),
        ),
        actions: [
          // 플래시 토글 버튼
          IconButton(
            icon: ValueListenableBuilder(
              valueListenable: _controller,
              builder: (context, state, child) {
                final isOn = state.torchState == TorchState.on;
                return Icon(
                  isOn
                      ? PhosphorIconsFill.flashlight
                      : PhosphorIconsRegular.flashlight,
                  color: Colors.white,
                );
              },
            ),
            onPressed: () => _controller.toggleTorch(),
          ),
        ],
      ),
      body: Stack(
        children: [
          // 카메라 뷰
          MobileScanner(controller: _controller, onDetect: _onDetect),

          // 오버레이 (어두운 배경)
          ColorFiltered(
            colorFilter: ColorFilter.mode(
              Colors.black.withOpacity(0.5),
              BlendMode.srcOut,
            ),
            child: Stack(
              children: [
                Container(
                  decoration: const BoxDecoration(
                    color: Colors.black,
                    backgroundBlendMode: BlendMode.dstOut,
                  ),
                ),
                Align(
                  alignment: Alignment.center,
                  child: Container(
                    height: 250,
                    width: 250,
                    decoration: BoxDecoration(
                      color: Colors.white,
                      borderRadius: BorderRadius.circular(12),
                    ),
                  ),
                ),
              ],
            ),
          ),

          // 스캔 가이드 테두리
          Center(
            child: Container(
              width: 250,
              height: 250,
              decoration: BoxDecoration(
                border: Border.all(color: Colors.white, width: 3),
                borderRadius: BorderRadius.circular(12),
              ),
              child: Stack(
                children: [
                  // 코너 가이드
                  ..._buildCornerGuides(),
                ],
              ),
            ),
          ),

          // 안내 텍스트
          Positioned(
            top: 100,
            left: 0,
            right: 0,
            child: Container(
              margin: const EdgeInsets.symmetric(horizontal: 40),
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: Colors.black.withOpacity(0.7),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(
                'OLaLA 채팅방 QR 코드를\n카메라에 비춰주세요',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 14,
                  fontWeight: FontWeight.w600,
                  height: 1.4,
                  shadows: [
                    Shadow(
                      color: Colors.black.withOpacity(0.8),
                      blurRadius: 4,
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  /// 코너 가이드 생성
  List<Widget> _buildCornerGuides() {
    const cornerSize = 20.0;
    const cornerWidth = 3.0;
    const color = Color(0xFF4683F6);

    return [
      // 왼쪽 위
      Positioned(
        top: 0,
        left: 0,
        child: Container(width: cornerSize, height: cornerWidth, color: color),
      ),
      Positioned(
        top: 0,
        left: 0,
        child: Container(width: cornerWidth, height: cornerSize, color: color),
      ),
      // 오른쪽 위
      Positioned(
        top: 0,
        right: 0,
        child: Container(width: cornerSize, height: cornerWidth, color: color),
      ),
      Positioned(
        top: 0,
        right: 0,
        child: Container(width: cornerWidth, height: cornerSize, color: color),
      ),
      // 왼쪽 아래
      Positioned(
        bottom: 0,
        left: 0,
        child: Container(width: cornerSize, height: cornerWidth, color: color),
      ),
      Positioned(
        bottom: 0,
        left: 0,
        child: Container(width: cornerWidth, height: cornerSize, color: color),
      ),
      // 오른쪽 아래
      Positioned(
        bottom: 0,
        right: 0,
        child: Container(width: cornerSize, height: cornerWidth, color: color),
      ),
      Positioned(
        bottom: 0,
        right: 0,
        child: Container(width: cornerWidth, height: cornerSize, color: color),
      ),
    ];
  }
}
