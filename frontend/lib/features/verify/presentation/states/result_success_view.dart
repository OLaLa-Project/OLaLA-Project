import 'package:flutter/material.dart';
import 'package:get/get.dart';
import 'package:phosphor_flutter/phosphor_flutter.dart';

import '../result_controller.dart';
import '../widgets/result_icon.dart';
import '../widgets/evidence_card_view.dart';
import '../widgets/share_button.dart';

class ResultSuccessView extends GetView<ResultController> {
  const ResultSuccessView({super.key});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final bg = isDark
        ? theme.colorScheme.surfaceVariant
        : const Color(0xFFF7F7F7);

    return Scaffold(
      backgroundColor: bg,
      appBar: AppBar(
        backgroundColor: isDark ? theme.colorScheme.surface : Colors.white,
        foregroundColor: isDark ? theme.colorScheme.onSurface : Colors.black,
        elevation: 0,
        surfaceTintColor: isDark ? theme.colorScheme.surface : Colors.white,
        toolbarHeight: 56,
        shape: Border(
          bottom: BorderSide(
            color: isDark
                ? theme.colorScheme.outlineVariant.withOpacity(0.7)
                : Colors.black.withOpacity( 0.06),
            width: 1,
          ),
        ),
        leading: IconButton(
          tooltip: '뒤로가기',
          icon: const Icon(
            PhosphorIconsRegular.caretLeft,
            size: 32,
          ),
          onPressed: () => Get.back(),
        ),
        title: const Text(
          'Result',
          style: TextStyle(
            fontSize: 30,
            fontWeight: FontWeight.w400,
          ),
        ),
        centerTitle: true,
        actions: [
          BookmarkIconButton(
            onPressed: controller.addBookmark,
          ),
          SettingsIconButton(
            onPressed: controller.openSettings,
          ),
        ],
      ),
      body: SafeArea(
        child: Stack(
          children: [
            Obx(() {
                    final verdict = controller.verdictType.value;
                    final confidence = controller.confidence.value.clamp(0.0, 1.0);

                    final headline = controller.successHeadline.value.isNotEmpty
                        ? controller.successHeadline.value
                        : _defaultHeadline(verdict);

                    final rawReason = controller.successReason.value.isNotEmpty
                        ? controller.successReason.value
                        : '근거를 바탕으로 결과를 정리했어요.\n아래 근거를 직접 확인해 주세요.';
                    // Remove (ev_...) citations and trim
                    final reason = rawReason
                        .replaceAll(RegExp(r'\s*\(?ev_[a-zA-Z0-9]+\)?'), '')
                        .trim();
                    final badgeText = controller.verdictBadgeText.value.isNotEmpty
                        ? controller.verdictBadgeText.value
                        : _defaultBadgeLabel(verdict);
                    final riskFlags = controller.resultRiskFlags.toList(growable: false);

                    final cards = controller.evidenceCards;

                    return ListView(
                      padding: const EdgeInsets.fromLTRB(20, 12, 20, 16),
                      children: [
                        const SizedBox(height: 6),

                        // ─────────────────────────────
                        // 1) 결과 아이콘
                        // ─────────────────────────────
                        Center(child: ResultIcon(verdict: verdict)),
                        const SizedBox(height: 14),

                        // ─────────────────────────────
                        // 2) Verdict Pill + Headline
                        // ─────────────────────────────
                        Center(
                          child: _VerdictPill(
                            verdict: verdict,
                            label: badgeText,
                          ),
                        ),
                        const SizedBox(height: 10),

                        Text(
                          headline,
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.headlineSmall?.copyWith(
                                fontWeight: FontWeight.w900,
                                height: 1.18,
                                color: const Color(0xFF111827),
                              ),
                        ),
                        const SizedBox(height: 12),

                        // ─────────────────────────────
                        // 3) Confidence Bar (브랜드 카드)
                        // ─────────────────────────────
                        _Card(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Icon(Icons.verified_outlined,
                                      size: 18, color: _toneColor(verdict)),
                                  const SizedBox(width: 8),
                                  Text(
                                    '신뢰도',
                                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                          fontWeight: FontWeight.w900,
                                          color: const Color(0xFF111827),
                                        ),
                                  ),
                                  const Spacer(),
                                  Text(
                                    '${(confidence * 100).round()}%',
                                    style: const TextStyle(
                                      fontWeight: FontWeight.w900,
                                      color: Color(0xFF111827),
                                    ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              _ConfidenceBar(
                                value: confidence,
                                tone: _toneColor(verdict),
                              ),
                              const SizedBox(height: 8),
                              Text(
                                _confidenceHint(verdict, confidence),
                                style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                      color: const Color(0xFF6B7280),
                                      fontWeight: FontWeight.w700,
                                      height: 1.35,
                                    ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 12),

                        // ─────────────────────────────
                        // (New) 검증 대상 (Original Claim)
                        // ─────────────────────────────
                        _Card(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Row(
                                children: [
                                  Icon(Icons.format_quote_rounded,
                                      size: 18, color: _toneColor(verdict)),
                                  const SizedBox(width: 8),
                                  Text(
                                    '핵심 검증 포인트',
                                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                          fontWeight: FontWeight.w900,
                                          color: const Color(0xFF111827),
                                        ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              Text(
                                controller.extractedClaim.value.isNotEmpty
                                    ? controller.extractedClaim.value
                                    : controller.userQuery.value,
                                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                                      color: const Color(0xFF374151),
                                      height: 1.48,
                                      fontWeight: FontWeight.w600,
                                    ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 12),

                        // ─────────────────────────────
                        // 4) 판단 이유 카드
                        // ─────────────────────────────
                        _Card(
                          child: Column(
                            children: [
                              Row(
                                children: [
                                  Icon(Icons.lightbulb_outlined,
                                      size: 18, color: _toneColor(verdict)),
                                  const SizedBox(width: 8),
                                  Text(
                                    '상세 분석 결과',
                                    style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                          fontWeight: FontWeight.w900,
                                          color: const Color(0xFF111827),
                                        ),
                                  ),
                                ],
                              ),
                              const SizedBox(height: 10),
                              Text(
                                reason,
                                textAlign: TextAlign.justify,
                                style: Theme.of(context).textTheme.bodyMedium?.copyWith(
                                      color: const Color(0xFF374151),
                                      height: 1.48,
                                      fontWeight: FontWeight.w600,
                                    ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),

                        if (riskFlags.isNotEmpty) ...[
                          _Card(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Row(
                                  children: [
                                    Icon(
                                      Icons.warning_amber_rounded,
                                      size: 18,
                                      color: _toneColor(verdict),
                                    ),
                                    const SizedBox(width: 8),
                                    Text(
                                      '주의 신호',
                                      style: Theme.of(context).textTheme.titleSmall?.copyWith(
                                            fontWeight: FontWeight.w900,
                                            color: const Color(0xFF111827),
                                          ),
                                    ),
                                  ],
                                ),
                                const SizedBox(height: 10),
                                Wrap(
                                  spacing: 8,
                                  runSpacing: 8,
                                  children: riskFlags
                                      .map((flag) => _RiskFlagChip(flag: flag))
                                      .toList(growable: false),
                                ),
                              ],
                            ),
                          ),
                          const SizedBox(height: 12),
                        ],

                        // ─────────────────────────────
                        // 5) 근거 리스트
                        // ─────────────────────────────
                        Row(
                          children: [
                            Text(
                              '근거',
                              style: Theme.of(context).textTheme.titleMedium?.copyWith(
                                    fontWeight: FontWeight.w900,
                                    color: const Color(0xFF111827),
                                  ),
                            ),
                            const SizedBox(width: 8),
                            _CountChip(count: cards.length),
                          ],
                        ),
                        const SizedBox(height: 10),

                        if (cards.isEmpty)
                          _EmptyEvidencePlaceholder()
                        else
                          ...cards.map(
                            (c) => Padding(
                              padding: const EdgeInsets.only(bottom: 10),
                              child: EvidenceCardView(card: c),
                            ),
                          ),

                        const SizedBox(height: 10),
                        Text(
                          '※ 결과는 참고용이며, 링크/출처를 직접 확인하는 것을 권장해요.',
                          textAlign: TextAlign.center,
                          style: Theme.of(context).textTheme.bodySmall?.copyWith(
                                color: const Color(0xFF6B7280),
                                fontWeight: FontWeight.w700,
                                height: 1.35,
                              ),
                        ),
                      ],
                    );
                  }),

            // ✅ 우하단 공유 버튼
            Positioned(
              right: 12,
              bottom: 12,
              child: ShareButton(onPressed: controller.shareResult),
            ),
          ],
        ),
      ),
      bottomNavigationBar: Container(
        decoration: BoxDecoration(
          color: isDark ? theme.colorScheme.surface : Colors.white,
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity( 0.06),
              blurRadius: 0,
              offset: const Offset(0, -1),
            ),
          ],
        ),
        child: NavigationBarTheme(
          data: NavigationBarThemeData(
            indicatorColor: Colors.transparent,
            overlayColor: MaterialStateProperty.all(Colors.transparent),
            backgroundColor: isDark ? theme.colorScheme.surface : Colors.white,
            iconTheme: MaterialStateProperty.resolveWith<IconThemeData>((states) {
              final selected = states.contains(MaterialState.selected);
              return IconThemeData(
                size: 32,
                color: selected
                    ? (isDark ? theme.colorScheme.onSurface : Colors.black)
                    : (isDark
                          ? theme.colorScheme.onSurfaceVariant
                          : const Color(0xff7a7a7a)),
              );
            }),
            labelTextStyle: MaterialStateProperty.resolveWith<TextStyle>((states) {
              final selected = states.contains(MaterialState.selected);
              return TextStyle(
                color: selected
                    ? (isDark ? theme.colorScheme.onSurface : Colors.black)
                    : (isDark
                          ? theme.colorScheme.onSurfaceVariant
                          : const Color(0xff7a7a7a)),
                fontSize: 12,
              );
            }),
          ),
          child: NavigationBar(
            selectedIndex: 1, // 검증(중앙) 탭 선택
            onDestinationSelected: (index) {
              if (index == 0) controller.goHistory();
              if (index == 1) controller.goHome();
              if (index == 2) controller.goBookmark();
            },
            destinations: const [
              NavigationDestination(
                icon: Icon(PhosphorIconsRegular.clockCounterClockwise),
                label: '히스토리',
              ),
              NavigationDestination(
                icon: Icon(PhosphorIconsRegular.magnifyingGlass),
                label: '검증',
              ),
              NavigationDestination(
                icon: Icon(PhosphorIconsRegular.bookmarkSimple),
                label: '북마크',
              ),
            ],
          ),
        ),
      ),
    );
  }

  String _defaultHeadline(VerdictType v) {
    switch (v) {
      case VerdictType.trueClaim:
        return '대체로 사실이에요';
      case VerdictType.falseClaim:
        return '사실과 달라요';
      case VerdictType.mixed:
        return '일부만 사실이에요';
      case VerdictType.unverified:
        return '판단하기 어려워요';
    }
  }

  String _defaultBadgeLabel(VerdictType v) {
    switch (v) {
      case VerdictType.trueClaim:
        return 'TRUE';
      case VerdictType.falseClaim:
        return 'FALSE';
      case VerdictType.mixed:
        return 'MIXED';
      case VerdictType.unverified:
        return 'UNVERIFIED';
    }
  }

  String _confidenceHint(VerdictType v, double c) {
    if (v == VerdictType.unverified) {
      return '근거가 부족하거나 상충돼요. 추가 출처 확인이 필요해요.';
    }
    if (c >= 0.85) return '근거가 충분해 보여요. 그래도 출처를 확인해 보세요.';
    if (c >= 0.65) return '근거는 있으나 일부 해석 여지가 있어요.';
    return '근거 신뢰도가 낮거나 편향 가능성이 있어요. 교차 확인을 권장해요.';
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
// Brand UI building blocks (파일 내부 private)
// ─────────────────────────────────────────

class _Card extends StatelessWidget {
  final Widget child;
  const _Card({required this.child});

  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(color: const Color(0xFFE6ECFF)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity( 0.04),
            blurRadius: 16,
            offset: const Offset(0, 8),
          ),
        ],
      ),
      child: child,
    );
  }
}

class _VerdictPill extends StatelessWidget {
  final VerdictType verdict;
  final String label;
  const _VerdictPill({required this.verdict, required this.label});

  @override
  Widget build(BuildContext context) {
    final s = _pillStyle(verdict);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 7),
      decoration: BoxDecoration(
        color: s.bg,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: s.border),
      ),
      child: Text(
        label,
        style: TextStyle(
          color: s.fg,
          fontWeight: FontWeight.w900,
          fontSize: 12,
          letterSpacing: 0.2,
        ),
      ),
    );
  }

  _PillStyle _pillStyle(VerdictType v) {
    switch (v) {
      case VerdictType.trueClaim:
        return const _PillStyle(
          bg: Color(0xFFE8F9EA),
          border: Color(0xFFB8F0C0),
          fg: Color(0xFF34C759),
        );
      case VerdictType.falseClaim:
        return const _PillStyle(
          bg: Color(0xFFFFEAEA),
          border: Color(0xFFFFC9C9),
          fg: Color(0xFFEF4444),
        );
      case VerdictType.mixed:
        return const _PillStyle(
          bg: Color(0xFFFFF4E6),
          border: Color(0xFFFFD9A6),
          fg: Color(0xFFF59E0B),
        );
      case VerdictType.unverified:
        return const _PillStyle(
          bg: Color(0xFFF2F4F7),
          border: Color(0xFFE4E7EC),
          fg: Color(0xFF667085),
        );
    }
  }
}

class _PillStyle {
  final Color bg;
  final Color border;
  final Color fg;
  const _PillStyle({
    required this.bg,
    required this.border,
    required this.fg,
  });
}

class _ConfidenceBar extends StatelessWidget {
  final double value; // 0~1
  final Color tone;
  const _ConfidenceBar({required this.value, required this.tone});

  @override
  Widget build(BuildContext context) {
    return ClipRRect(
      borderRadius: BorderRadius.circular(999),
      child: Container(
        height: 10,
        color: const Color(0xFFEFF3FF),
        child: Align(
          alignment: Alignment.centerLeft,
          child: FractionallySizedBox(
            widthFactor: value.clamp(0.0, 1.0),
            child: Container(
              color: tone,
            ),
          ),
        ),
      ),
    );
  }
}

class _CountChip extends StatelessWidget {
  final int count;
  const _CountChip({required this.count});

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: const Color(0xFFE9F3FF),
        borderRadius: BorderRadius.circular(999),
      ),
      child: Text(
        '$count개',
        style: const TextStyle(
          color: Color(0xFF3478F6),
          fontWeight: FontWeight.w900,
          fontSize: 12,
        ),
      ),
    );
  }
}

class _RiskFlagChip extends StatelessWidget {
  final String flag;
  const _RiskFlagChip({required this.flag});

  String _translateFlag(String f) {
    switch (f.toUpperCase()) {
      case 'LOW_EVIDENCE': return '근거 부족';
      case 'NO_SKEPTIC_EVIDENCE': return '반박 근거 없음';
      case 'UNBALANCED_STANCE_EVIDENCE': return '근거 편향됨';
      case 'NO_VERIFIED_CITATIONS': return '인용 없음';
      case 'LOW_CONFIDENCE': return '신뢰도 낮음';
      default: return f;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(
        color: const Color(0xFFFFF4E6),
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: const Color(0xFFFFD9A6)),
      ),
      child: Text(
        _translateFlag(flag),
        style: const TextStyle(
          color: Color(0xFFB45309),
          fontWeight: FontWeight.w800,
          fontSize: 11,
        ),
      ),
    );
  }
}

class _EmptyEvidencePlaceholder extends StatelessWidget {
  @override
  Widget build(BuildContext context) {
    return _Card(
      child: Text(
        '표시할 근거가 아직 없어요.',
        textAlign: TextAlign.center,
        style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: const Color(0xFF6B7280),
              fontWeight: FontWeight.w700,
            ),
      ),
    );
  }
}

// ═══════════════════════════════════════════════════════════════════════════════
// 설정 아이콘 버튼 (눌리는 동안 아이콘/색 변경)
// ═══════════════════════════════════════════════════════════════════════════════

class SettingsIconButton extends StatefulWidget {
  final VoidCallback onPressed;
  const SettingsIconButton({super.key, required this.onPressed});

  @override
  State<SettingsIconButton> createState() => _SettingsIconButtonState();
}

class _SettingsIconButtonState extends State<SettingsIconButton> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      behavior: HitTestBehavior.opaque,
      onTapDown: (_) => setState(() => _pressed = true),
      onTapUp: (_) {
        setState(() => _pressed = false);
        widget.onPressed();
      },
      onTapCancel: () => setState(() => _pressed = false),
      child: Padding(
        padding: const EdgeInsets.symmetric(horizontal: 8),
        child: Icon(
          _pressed ? PhosphorIconsFill.gear : PhosphorIconsRegular.gear,
          size: 32,
          color: _pressed ? Colors.black : null,
        ),
      ),
    );
  }
}

class BookmarkIconButton extends StatefulWidget {
  final VoidCallback onPressed;
  const BookmarkIconButton({super.key, required this.onPressed});

  @override
  State<BookmarkIconButton> createState() => _BookmarkIconButtonState();
}

class _BookmarkIconButtonState extends State<BookmarkIconButton> {
  bool _pressed = false;

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: '북마크 추가',
      child: GestureDetector(
        behavior: HitTestBehavior.opaque,
        onTapDown: (_) => setState(() => _pressed = true),
        onTapUp: (_) {
          setState(() => _pressed = false);
          widget.onPressed();
        },
        onTapCancel: () => setState(() => _pressed = false),
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 8),
          child: Icon(
            _pressed
                ? PhosphorIconsFill.bookmarkSimple
                : PhosphorIconsRegular.bookmarkSimple,
            size: 30,
            color: _pressed
                ? const Color(0xFF7DB7FF)
                : const Color(0xFF7DB7FF),
          ),
        ),
      ),
    );
  }
}
