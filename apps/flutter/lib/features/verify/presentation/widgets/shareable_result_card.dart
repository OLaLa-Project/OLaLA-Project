import 'package:flutter/material.dart';
import '../result_controller.dart';
import '../widgets/result_icon.dart';
import '../../models/evidence_card.dart';

/// 공유용 이미지로 변환될 카드
/// (실제 화면에는 보이지 않고, screenshot 패키지로 캡처됨)
class ShareableResultCard extends StatelessWidget {
  final VerdictType verdict;
  final String headline;
  final double confidence;
  final String reason;
  final int evidenceCount;
  final String userQuery;
  final List<EvidenceCard> evidenceCards;

  const ShareableResultCard({
    super.key,
    required this.verdict,
    required this.headline,
    required this.confidence,
    required this.reason,
    required this.evidenceCount,
    this.userQuery = '',
    this.evidenceCards = const [],
  });

  @override
  Widget build(BuildContext context) {
    return Container(
      width: 800, // 고정 크기 (소셜 미디어 최적화)
      padding: const EdgeInsets.all(40),
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topCenter,
          end: Alignment.bottomCenter,
          colors: [
            Color(0xFF5A87FF), // OLaLA 브랜드 Splash Blue
            Color(0xFF4683F6), // OLaLA 브랜드 Primary Blue
          ],
        ),
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          // ─────────────────────────────
          // 상단: OLaLA 로고
          // ─────────────────────────────
          Row(
            children: [
              Image.asset(
                'assets/images/brand_logo.png',
                width: 52,
                height: 52,
                fit: BoxFit.contain,
              ),
              const SizedBox(width: 14),
              const Text(
                'OLaLA',
                style: TextStyle(
                  fontSize: 36,
                  fontWeight: FontWeight.w900,
                  color: Colors.white,
                  letterSpacing: -0.5,
                ),
              ),
            ],
          ),

          const SizedBox(height: 24),

          // ─────────────────────────────
          // 사용자 질문 (있는 경우만 표시)
          // ─────────────────────────────
          if (userQuery.isNotEmpty) ...[
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
              decoration: BoxDecoration(
                color: Colors.white.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(12),
                border: Border.all(color: Colors.white.withValues(alpha: 0.3)),
              ),
              child: RichText(
                textAlign: TextAlign.center,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                text: TextSpan(
                  children: [
                    // 왼쪽 쌍따옴표 (크고 투명도 있음)
                    TextSpan(
                      text: '\u201C',
                      style: TextStyle(
                        fontSize: 36,
                        fontWeight: FontWeight.w900,
                        color: Colors.white.withValues(alpha: 0.6),
                        height: 1.0,
                      ),
                    ),
                    // 본문 텍스트
                    TextSpan(
                      text: userQuery,
                      style: const TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.w600,
                        color: Colors.white,
                        height: 1.3,
                      ),
                    ),
                    // 오른쪽 쌍따옴표 (크고 투명도 있음)
                    TextSpan(
                      text: '\u201D',
                      style: TextStyle(
                        fontSize: 36,
                        fontWeight: FontWeight.w900,
                        color: Colors.white.withValues(alpha: 0.6),
                        height: 1.0,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),
          ],

          // ─────────────────────────────
          // 중앙: 결과 카드 (흰색 배경)
          // ─────────────────────────────
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 30),
            child: Container(
              padding: const EdgeInsets.all(30),
            decoration: BoxDecoration(
              color: Colors.white,
              borderRadius: BorderRadius.circular(24),
              boxShadow: [
                BoxShadow(
                  color: Colors.black.withValues(alpha: 0.15),
                  blurRadius: 30,
                  offset: const Offset(0, 15),
                ),
              ],
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                // 결과 아이콘
                Center(child: ResultIcon(verdict: verdict, size: 100)),
                const SizedBox(height: 20),

                // Verdict Pill
                Center(child: _VerdictPill(verdict: verdict)),
                const SizedBox(height: 16),

                // Headline (메인 텍스트)
                Text(
                  headline,
                  textAlign: TextAlign.center,
                  style: const TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.w800,
                    color: Color(0xFF111827),
                    height: 1.25,
                  ),
                ),

                const SizedBox(height: 24),

                // 신뢰도 바
                Container(
                  padding: const EdgeInsets.all(16),
                  decoration: BoxDecoration(
                    color: const Color(0xFFF7F7F7),
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Row(
                            children: [
                              Icon(
                                Icons.verified_outlined,
                                size: 20,
                                color: _toneColor(verdict),
                              ),
                              const SizedBox(width: 6),
                              const Text(
                                '신뢰도',
                                style: TextStyle(
                                  fontSize: 16,
                                  fontWeight: FontWeight.w800,
                                  color: Color(0xFF111827),
                                ),
                              ),
                            ],
                          ),
                          Text(
                            '${(confidence * 100).round()}%',
                            style: TextStyle(
                              fontSize: 22,
                              fontWeight: FontWeight.w900,
                              color: _toneColor(verdict),
                            ),
                          ),
                        ],
                      ),
                      const SizedBox(height: 12),
                      _ConfidenceBar(
                        value: confidence,
                        tone: _toneColor(verdict),
                      ),
                      const SizedBox(height: 10),
                      Row(
                        children: [
                          Icon(
                            Icons.lightbulb_outlined,
                            size: 16,
                            color: _toneColor(verdict),
                          ),
                          const SizedBox(width: 6),
                          Text(
                            '분석 근거 $evidenceCount개',
                            style: const TextStyle(
                              fontSize: 13,
                              fontWeight: FontWeight.w600,
                              color: Color(0xFF667085),
                            ),
                          ),
                        ],
                      ),
                    ],
                  ),
                ),

                const SizedBox(height: 16),

                // ─────────────────────────────
                // 요약 (Reason)
                // ─────────────────────────────
                if (reason.isNotEmpty) ...[
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: const Color(0xFFF7F7F7),
                      borderRadius: BorderRadius.circular(10),
                    ),
                    child: Text(
                      reason,
                      style: const TextStyle(
                        fontSize: 12,
                        fontWeight: FontWeight.w600,
                        color: Color(0xFF374151),
                        height: 1.4,
                      ),
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                    ),
                  ),
                ],
              ],
            ),
            ),
          ),

          const SizedBox(height: 20),

          // ─────────────────────────────
          // 주요 근거 (Top 2)
          // ─────────────────────────────
          if (evidenceCards.isNotEmpty) ...[
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 30),
              child: Container(
                padding: const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(16),
                boxShadow: [
                  BoxShadow(
                    color: Colors.black.withValues(alpha: 0.1),
                    blurRadius: 20,
                    offset: const Offset(0, 10),
                  ),
                ],
              ),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Row(
                    children: [
                      Icon(
                        Icons.fact_check_rounded,
                        size: 18,
                        color: Color(0xFF4683F6),
                      ),
                      SizedBox(width: 6),
                      Text(
                        '주요 근거',
                        style: TextStyle(
                          fontSize: 14,
                          fontWeight: FontWeight.w900,
                          color: Color(0xFF111827),
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  ...evidenceCards
                      .take(2)
                      .map(
                        (evidence) => Padding(
                          padding: const EdgeInsets.only(bottom: 10),
                          child: _EvidenceItem(evidence: evidence),
                        ),
                      ),
                ],
              ),
              ),
            ),
            const SizedBox(height: 20),
          ],

          // ─────────────────────────────
          // 하단: 앱 다운로드 안내 (흰색 텍스트)
          // ─────────────────────────────
          const Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(Icons.smartphone_rounded, size: 20, color: Colors.white),
              SizedBox(width: 8),
              Text(
                '자세한 내용은 OLaLA 앱에서 확인하세요',
                style: TextStyle(
                  fontSize: 14,
                  fontWeight: FontWeight.w700,
                  color: Colors.white,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  Color _toneColor(VerdictType v) {
    switch (v) {
      case VerdictType.trueClaim:
        return const Color(0xFF34C759);
      case VerdictType.falseClaim:
        return const Color(0xFFEF4444);
      case VerdictType.mixed:
        return const Color(0xFFF59E0B);
      case VerdictType.unverified:
        return const Color(0xFF667085);
    }
  }
}

// ─────────────────────────────────────────
// Verdict Pill (공유 이미지용)
// ─────────────────────────────────────────

class _VerdictPill extends StatelessWidget {
  final VerdictType verdict;
  const _VerdictPill({required this.verdict});

  @override
  Widget build(BuildContext context) {
    final s = _pillStyle(verdict);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 10),
      decoration: BoxDecoration(
        color: s.bg,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: s.border, width: 2),
      ),
      child: Text(
        s.label,
        style: TextStyle(
          color: s.fg,
          fontWeight: FontWeight.w900,
          fontSize: 16,
          letterSpacing: 0.5,
        ),
      ),
    );
  }

  _PillStyle _pillStyle(VerdictType v) {
    switch (v) {
      case VerdictType.trueClaim:
        return const _PillStyle(
          label: 'TRUE',
          bg: Color(0xFFE8F9EA),
          border: Color(0xFFB8F0C0),
          fg: Color(0xFF34C759),
        );
      case VerdictType.falseClaim:
        return const _PillStyle(
          label: 'FALSE',
          bg: Color(0xFFFFEAEA),
          border: Color(0xFFFFC9C9),
          fg: Color(0xFFEF4444),
        );
      case VerdictType.mixed:
        return const _PillStyle(
          label: 'MIXED',
          bg: Color(0xFFFFF4E6),
          border: Color(0xFFFFD9A6),
          fg: Color(0xFFF59E0B),
        );
      case VerdictType.unverified:
        return const _PillStyle(
          label: 'UNVERIFIED',
          bg: Color(0xFFF2F4F7),
          border: Color(0xFFE4E7EC),
          fg: Color(0xFF667085),
        );
    }
  }
}

class _PillStyle {
  final String label;
  final Color bg;
  final Color border;
  final Color fg;
  const _PillStyle({
    required this.label,
    required this.bg,
    required this.border,
    required this.fg,
  });
}

// ─────────────────────────────────────────
// Confidence Bar (공유 이미지용)
// ─────────────────────────────────────────

class _ConfidenceBar extends StatelessWidget {
  final double value;
  final Color tone;
  const _ConfidenceBar({required this.value, required this.tone});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(999),
      child: Container(
        height: 14,
        decoration: BoxDecoration(
          color: const Color(0xFFEFF3FF),
          borderRadius: BorderRadius.circular(999),
        ),
        child: Align(
          alignment: Alignment.centerLeft,
          child: FractionallySizedBox(
            widthFactor: value.clamp(0.0, 1.0),
            child: Container(
              decoration: BoxDecoration(
                color: tone,
                borderRadius: BorderRadius.circular(999),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

// ─────────────────────────────────────────
// Evidence Item (공유 이미지용)
// ─────────────────────────────────────────

class _EvidenceItem extends StatelessWidget {
  final EvidenceCard evidence;
  const _EvidenceItem({required this.evidence});

  @override
  Widget build(BuildContext context) {
    final urlText = _getShortUrl(evidence.url);

    return Container(
      padding: const EdgeInsets.all(10),
      decoration: BoxDecoration(
        color: const Color(0xFFF7F7F7),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFFE6ECFF)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _StanceIcon(stance: evidence.stance ?? 'neutral'),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  evidence.source ?? '출처 미상',
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                    color: Color(0xFF4683F6),
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
          const SizedBox(height: 5),
          Text(
            evidence.title ?? '제목 없음',
            style: const TextStyle(
              fontSize: 12,
              fontWeight: FontWeight.w700,
              color: Color(0xFF111827),
            ),
            maxLines: 2,
            overflow: TextOverflow.ellipsis,
          ),
          if (urlText.isNotEmpty) ...[
            const SizedBox(height: 4),
            Row(
              children: [
                const Icon(
                  Icons.link_rounded,
                  size: 10,
                  color: Color(0xFF667085),
                ),
                const SizedBox(width: 4),
                Expanded(
                  child: Text(
                    urlText,
                    style: const TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w600,
                      color: Color(0xFF667085),
                    ),
                    maxLines: 1,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
              ],
            ),
          ],
        ],
      ),
    );
  }

  String _getShortUrl(String? url) {
    if (url == null || url.isEmpty) return '';

    try {
      final uri = Uri.parse(url);
      return uri.host +
          (uri.path.isNotEmpty && uri.path != '/' ? uri.path : '');
    } catch (_) {
      return url;
    }
  }
}

// ─────────────────────────────────────────
// Stance Icon (입장 아이콘)
// ─────────────────────────────────────────

class _StanceIcon extends StatelessWidget {
  final String stance;
  const _StanceIcon({required this.stance});

  @override
  Widget build(BuildContext context) {
    final icon = _getIcon();
    final color = _getColor();

    return Container(
      width: 20,
      height: 20,
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.15),
        shape: BoxShape.circle,
      ),
      child: Icon(icon, size: 12, color: color),
    );
  }

  IconData _getIcon() {
    switch (stance) {
      case 'support':
        return Icons.check_circle_rounded;
      case 'refute':
        return Icons.cancel_rounded;
      case 'neutral':
        return Icons.remove_circle_rounded;
      default:
        return Icons.help_rounded;
    }
  }

  Color _getColor() {
    switch (stance) {
      case 'support':
        return const Color(0xFF3478F6);
      case 'refute':
        return const Color(0xFFEF4444);
      case 'neutral':
        return const Color(0xFFF59E0B);
      default:
        return const Color(0xFF667085);
    }
  }
}
