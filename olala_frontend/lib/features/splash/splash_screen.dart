import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'splash_controller.dart';

class SplashScreen extends GetView<SplashController> {
  const SplashScreen({super.key});

  static const Color _bgColor = Color.fromARGB(255, 90, 135, 255);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: _bgColor,
      body: SafeArea(
        child: LayoutBuilder(
          builder: (context, constraints) {
            // ✅ 차분 톤: 기기별로 로고 크기 약간만 유연하게
            final shortest = constraints.biggest.shortestSide;
            final logoSize = (shortest * 0.18).clamp(140.0, 168.0);

            return Center(
              // ✅ Optical center: 정중앙보다 살짝 위가 더 안정적으로 보임
              child: Transform.translate(
                offset: const Offset(0, -20),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    // ✅ 로고: 먼저 "툭" (Fade + 미세 Scale)
                    AnimatedBuilder(
                      animation: controller.controller,
                      builder: (_, child) {
                        final t = controller.reveal.value.clamp(0.0, 1.0);

                        // 로고는 조금 더 먼저/빠르게 존재감
                        final logoT = Curves.easeOut.transform(
                          (t / 0.65).clamp(0.0, 1.0),
                        );

                        // 차분 톤: 스케일 변화는 아주 미세하게
                        final scale = 0.97 + (0.03 * logoT); // 0.97 -> 1.0

                        return Opacity(
                          opacity: logoT,
                          child: Transform.scale(scale: scale, child: child),
                        );
                      },
                      child: Image.asset(
                        SplashController.logoAssetPath,
                        width: logoSize,
                        height: logoSize,
                      ),
                    ),

                    const SizedBox(height: 14),

                    // ✅ 텍스트: "툭" + 아주 살짝 왼→오 (차분하게)
                    AnimatedBuilder(
                      animation: controller.controller,
                      builder: (_, __) {
                        final t = controller.reveal.value.clamp(0.0, 1.0);

                        // 로고 다음에 나오도록 살짝 지연
                        final textT = Curves.easeOutCubic.transform(
                          ((t - 0.22) / 0.78).clamp(0.0, 1.0),
                        );

                        // 차분 톤: 이동량 작게(-10px), 스케일도 미세(0.99->1.0)
                        final dx = (-10.0) * (1.0 - textT);
                        final scale = 0.99 + (0.01 * textT);

                        return Opacity(
                          opacity: textT,
                          child: Transform.translate(
                            offset: Offset(dx, 0),
                            child: Transform.scale(
                              scale: scale,
                              child: const Text(
                                'OLaLA',
                                style: TextStyle(
                                  fontSize: 24,
                                  fontWeight: FontWeight.w600, // 차분/신뢰
                                  letterSpacing: 0.3, // 워드마크 정돈
                                  color: Colors.white,
                                ),
                              ),
                            ),
                          ),
                        );
                      },
                    ),
                  ],
                ),
              ),
            );
          },
        ),
      ),
    );
  }
}
