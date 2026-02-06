import 'dart:math' as math;

import 'package:flutter/material.dart';

import 'widgets/tutorial_content.dart';

class _HelpBrand {
  static const Color blue = Color(0xFF4683F6);
  static const Color blueLight = Color(0xFF5A87FF);
  static const Color ink = Color(0xFF111827);
  static const Color inkSubtle = Color(0xFF5C6475);
  static const Color surface = Colors.white;
  static const Color border = Color(0xFFE6ECFF);

  static const LinearGradient headerGradient = LinearGradient(
    begin: Alignment.topLeft,
    end: Alignment.bottomRight,
    colors: [blueLight, blue],
  );
}

const Set<GuideTarget> _bottomNavTargets = {
  GuideTarget.navHistory,
  GuideTarget.navVerify,
  GuideTarget.navBookmark,
};

class HelpScreen extends StatefulWidget {
  final Map<GuideTarget, Rect?> rects;
  final List<GuideItem> items;

  const HelpScreen({
    super.key,
    required this.rects,
    this.items = TutorialContent.homeInputGuideItems,
  });

  @override
  State<HelpScreen> createState() => _HelpScreenState();
}

class _HelpScreenState extends State<HelpScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _fadeController;
  late final Animation<double> _fadeOpacity;
  bool _closing = false;
  final Map<GuideTarget, Size> _labelSizes = {};

  static const double _headerBaseHeight = 64;
  static const double _footerBaseHeight = 92;

  @override
  void initState() {
    super.initState();

    // 페이드 애니메이션
    _fadeController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 300),
    )..forward();
    _fadeOpacity = CurvedAnimation(
      parent: _fadeController,
      curve: Curves.easeOutCubic,
    );
  }

  @override
  void dispose() {
    _fadeController.dispose();
    super.dispose();
  }

  Future<void> _close() async {
    if (_closing) return;
    _closing = true;
    try {
      await _fadeController.reverse();
    } catch (_) {}
    if (mounted) Navigator.of(context).pop();
  }

  List<GuideItem> _getEffectiveItems() {
    final effective = <GuideItem>[];
    for (final it in widget.items) {
      final r = widget.rects[it.target];
      if (r != null && r.width > 0 && r.height > 0) {
        effective.add(it);
      }
    }
    return effective;
  }

  void _updateLabelSize(GuideTarget target, Size size) {
    final prev = _labelSizes[target];
    if (prev == null ||
        (prev.width - size.width).abs() > 0.5 ||
        (prev.height - size.height).abs() > 0.5) {
      setState(() => _labelSizes[target] = size);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final brightness = theme.brightness;
    final isDark = brightness == Brightness.dark;
    final media = MediaQuery.of(context);
    final size = media.size;
    final safe = media.padding;

    final effectiveItems = _getEffectiveItems();
    if (effectiveItems.isEmpty) {
      Navigator.of(context).pop();
      return const SizedBox.shrink();
    }

    // 반응형 크기 계산
    final screenWidth = size.width;
    final titleFontSize = _responsiveFontSize(14, screenWidth);
    final descFontSize = _responsiveFontSize(11, screenWidth);

    final headerHeight =
        safe.top + _responsiveValue(_headerBaseHeight, screenWidth);
    final footerHeight =
        safe.bottom + _responsiveValue(_footerBaseHeight, screenWidth);

    final labelPositions = _LabelLayout.resolvePositions(
      items: effectiveItems,
      rects: widget.rects,
      labelSizes: _labelSizes,
      screenSize: size,
      headerHeight: headerHeight,
      footerHeight: footerHeight,
    );

    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, result) async {
        if (!didPop) {
          await _close();
        }
      },
      child: FadeTransition(
        opacity: _fadeOpacity,
        child: Material(
          color: Colors.transparent,
          child: Stack(
            children: [
              // 배경 스크림 + 모든 하이라이트
              Positioned.fill(
                child: CustomPaint(
                  painter: _CoachPainter(
                    items: effectiveItems,
                    rects: widget.rects,
                    isDark: isDark,
                    labelSizes: Map.of(_labelSizes),
                    labelPositions: labelPositions,
                    headerHeight: headerHeight,
                    footerHeight: footerHeight,
                    safeAreaBottom: safe.bottom,
                  ),
                ),
              ),

              // 상단 헤더 - 닫기 버튼
              SafeArea(
                child: Padding(
                  padding: EdgeInsets.fromLTRB(
                    _responsiveValue(16, screenWidth),
                    _responsiveValue(10, screenWidth),
                    _responsiveValue(16, screenWidth),
                    _responsiveValue(8, screenWidth),
                  ),
                  child: Row(
                    children: [_CloseButton(onTap: _close, isDark: isDark)],
                  ),
                ),
              ),

              // 모든 라벨들
              ...effectiveItems.map((item) {
                final rect = widget.rects[item.target]!;
                return _CoachLabel(
                  target: item.target,
                  rect: rect,
                  screenSize: size,
                  title: item.title,
                  description: item.description,
                  placement: item.placement,
                  isDark: isDark,
                  titleFontSize: titleFontSize,
                  descFontSize: descFontSize,
                  knownSize: _labelSizes[item.target],
                  resolvedTopLeft: labelPositions[item.target],
                  headerHeight: headerHeight,
                  footerHeight: footerHeight,
                  onSizeCalculated: (size) =>
                      _updateLabelSize(item.target, size),
                );
              }),
            ],
          ),
        ),
      ),
    );
  }

  double _responsiveFontSize(double baseSize, double screenWidth) {
    if (screenWidth > 600) {
      return baseSize * 1.1; // 태블릿
    } else if (screenWidth < 360) {
      return baseSize * 0.9; // 작은 폰
    }
    return baseSize;
  }

  double _responsiveValue(double baseValue, double screenWidth) {
    if (screenWidth > 600) {
      return baseValue * 1.2;
    } else if (screenWidth < 360) {
      return baseValue * 0.85;
    }
    return baseValue;
  }
}

/// 닫기 버튼
class _CloseButton extends StatelessWidget {
  final VoidCallback onTap;
  final bool isDark;

  const _CloseButton({required this.onTap, required this.isDark});

  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(14),
      onTap: onTap,
      child: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(14),
          border: Border.all(
            color: isDark
                ? Colors.white.withOpacity( 0.18)
                : _HelpBrand.border,
            width: 1.2,
          ),
          color: isDark
              ? Colors.white.withOpacity( 0.08)
              : Colors.white.withOpacity( 0.95),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withOpacity( 0.12),
              blurRadius: 10,
              offset: const Offset(0, 4),
            ),
          ],
        ),
        child: Center(
          child: Icon(
            Icons.close_rounded,
            color: isDark ? Colors.white : _HelpBrand.ink,
            size: 20,
          ),
        ),
      ),
    );
  }
}

class _LabelMetrics {
  static const double defaultHeight = 68;
  static const double _minBottomNavWidth = 85;

  static double maxWidthFor(GuideTarget target, double screenWidth) {
    final base = _baseWidth(screenWidth);
    if (_bottomNavTargets.contains(target)) {
      final padding = screenWidth > 600 ? 16.0 : 12.0;
      const columnGap = 12.0;
      final twoColumnMax = (screenWidth - padding * 2 - columnGap) / 2;
      final capped = math.min(base, twoColumnMax);
      return capped < _minBottomNavWidth ? _minBottomNavWidth : capped;
    }
    return base;
  }

  static double _baseWidth(double screenWidth) {
    if (screenWidth > 600) {
      return 110.0; // 태블릿
    } else if (screenWidth < 360) {
      return screenWidth * 0.35; // 작은 폰 (가독성 중심)
    }
    return 85.0; // 모바일 기본 크기
  }

  static EdgeInsets paddingFor(double screenWidth) {
    if (screenWidth > 600) {
      return const EdgeInsets.fromLTRB(10, 8, 10, 8);
    } else if (screenWidth < 360) {
      return const EdgeInsets.fromLTRB(6, 5, 6, 5);
    }
    return const EdgeInsets.fromLTRB(8, 6, 8, 6);
  }

  static Size estimatedSize(
    GuideTarget target,
    double screenWidth,
    Size? knownSize,
  ) {
    if (knownSize != null) {
      return knownSize;
    }
    return Size(maxWidthFor(target, screenWidth), defaultHeight);
  }
}

/// 라벨(말풍선) - 동적 크기 계산 및 반응형 디자인
class _CoachLabel extends StatefulWidget {
  final GuideTarget target;
  final Rect rect;
  final Size screenSize;
  final String title;
  final String description;
  final LabelPlacement placement;
  final bool isDark;
  final double titleFontSize;
  final double descFontSize;
  final Size? knownSize;
  final Offset? resolvedTopLeft;
  final double headerHeight;
  final double footerHeight;
  final Function(Size)? onSizeCalculated;

  const _CoachLabel({
    super.key,
    required this.target,
    required this.rect,
    required this.screenSize,
    required this.title,
    required this.description,
    required this.placement,
    required this.isDark,
    required this.titleFontSize,
    required this.descFontSize,
    required this.knownSize,
    required this.resolvedTopLeft,
    required this.headerHeight,
    required this.footerHeight,
    this.onSizeCalculated,
  });

  @override
  State<_CoachLabel> createState() => _CoachLabelState();
}

class _CoachLabelState extends State<_CoachLabel>
    with SingleTickerProviderStateMixin {
  late final AnimationController _slideController;
  late final Animation<Offset> _slideOffset;
  final GlobalKey _contentKey = GlobalKey();

  @override
  void initState() {
    super.initState();
    _slideController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 400),
    )..forward();

    _slideOffset = Tween<Offset>(begin: const Offset(0, 0.1), end: Offset.zero)
        .animate(
          CurvedAnimation(parent: _slideController, curve: Curves.easeOutCubic),
        );

    // 크기 계산
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _calculateSize();
    });
  }

  @override
  void dispose() {
    _slideController.dispose();
    super.dispose();
  }

  void _calculateSize() {
    final renderBox =
        _contentKey.currentContext?.findRenderObject() as RenderBox?;
    if (renderBox != null && widget.onSizeCalculated != null) {
      final size = renderBox.size;
      widget.onSizeCalculated!(size);
    }
  }

  @override
  Widget build(BuildContext context) {
    // 반응형 최대 너비
    final maxWidth = _LabelMetrics.maxWidthFor(
      widget.target,
      widget.screenSize.width,
    );
    final minWidth = math.min(140.0, maxWidth);
    final cardPadding = _LabelMetrics.paddingFor(widget.screenSize.width);

    // 초기 예상 크기 (실제 측정 전)
    final estimatedSize = _LabelMetrics.estimatedSize(
      widget.target,
      widget.screenSize.width,
      widget.knownSize,
    );

    final labelTopLeft =
        widget.resolvedTopLeft ??
        _LabelGeometry.labelTopLeft(
          rect: widget.rect,
          placement: widget.placement,
          labelSize: estimatedSize,
          screenSize: widget.screenSize,
          headerHeight: widget.headerHeight,
          footerHeight: widget.footerHeight,
        );

    return Positioned(
      left: labelTopLeft.dx,
      top: labelTopLeft.dy,
      child: SlideTransition(
        position: _slideOffset,
        child: FadeTransition(
          opacity: _slideController,
          child: ConstrainedBox(
            constraints: BoxConstraints(maxWidth: maxWidth, minWidth: minWidth),
            child: Container(
              key: _contentKey,
              padding: cardPadding,
              decoration: BoxDecoration(
                color: widget.isDark
                    ? const Color(0xFF0F172A).withOpacity( 0.96)
                    : _HelpBrand.surface.withOpacity( 0.98),
                borderRadius: BorderRadius.circular(18),
                border: Border.all(
                  color: widget.isDark
                      ? Colors.white.withOpacity( 0.12)
                      : _HelpBrand.border,
                  width: 1.1,
                ),
              ),
              child: Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // 제목
                  Text(
                    widget.title,
                    style: TextStyle(
                      fontSize: widget.titleFontSize,
                      fontWeight: FontWeight.w900,
                      letterSpacing: -0.2,
                      color: widget.isDark ? Colors.white : _HelpBrand.ink,
                    ),
                  ),
                  const SizedBox(height: 8),
                  // 설명
                  Text(
                    widget.description,
                    style: TextStyle(
                      fontSize: widget.descFontSize,
                      height: 1.4,
                      // 접근성 개선: 명도 대비 향상 (0.72 → 0.85)
                      color: widget.isDark
                          ? Colors.white.withOpacity( 0.82)
                          : _HelpBrand.inkSubtle,
                      letterSpacing: -0.1,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// 라벨 위치 계산 (충돌 방지 로직 포함)
class _LabelGeometry {
  static Offset labelTopLeft({
    required Rect rect,
    required LabelPlacement placement,
    required Size labelSize,
    required Size screenSize,
    required double headerHeight,
    required double footerHeight,
  }) {
    // 반응형 간격 (라벨 간격 증가로 겹침 방지)
    final gap = screenSize.width > 600 ? 30.0 : 26.0;

    double x;
    double y;

    switch (placement) {
      case LabelPlacement.topLeft:
        x = rect.left;
        y = rect.top - gap - labelSize.height;
        break;
      case LabelPlacement.topRight:
        x = rect.right - labelSize.width;
        y = rect.top - gap - labelSize.height;
        break;
      case LabelPlacement.bottomLeft:
        x = rect.left;
        y = rect.bottom + gap;
        break;
      case LabelPlacement.bottomRight:
        x = rect.right - labelSize.width;
        y = rect.bottom + gap;
        break;
      case LabelPlacement.left:
        x = rect.left - gap - labelSize.width;
        y = rect.top;
        break;
      case LabelPlacement.right:
        x = rect.right + gap;
        y = rect.top;
        break;
      case LabelPlacement.top:
        x = rect.center.dx - labelSize.width / 2;
        y = rect.top - gap - labelSize.height;
        break;
      case LabelPlacement.bottom:
        x = rect.center.dx - labelSize.width / 2;
        y = rect.bottom + gap;
        break;
    }

    // 화면 경계 내로 제한 (충돌 방지)
    final padding = screenSize.width > 600 ? 16.0 : 12.0;
    final minX = padding;
    final maxX = screenSize.width - padding - labelSize.width;
    final minY = headerHeight;
    final maxY = screenSize.height - footerHeight - labelSize.height;

    x = x.clamp(minX, maxX.clamp(minX, screenSize.width - padding));
    y = y.clamp(minY, maxY.clamp(minY, screenSize.height - padding));

    return Offset(x, y);
  }

  static Offset labelAnchor({
    required Offset labelTopLeft,
    required Size labelSize,
    required LabelPlacement placement,
  }) {
    // placement에 따라 정확한 앵커 위치 계산
    switch (placement) {
      case LabelPlacement.topLeft:
        return Offset(
          labelTopLeft.dx + labelSize.width * 0.2,
          labelTopLeft.dy + labelSize.height,
        );
      case LabelPlacement.top:
        return Offset(
          labelTopLeft.dx + labelSize.width * 0.5,
          labelTopLeft.dy + labelSize.height,
        );
      case LabelPlacement.topRight:
        return Offset(
          labelTopLeft.dx + labelSize.width * 0.8,
          labelTopLeft.dy + labelSize.height,
        );
      case LabelPlacement.bottomLeft:
        return Offset(labelTopLeft.dx + labelSize.width * 0.2, labelTopLeft.dy);
      case LabelPlacement.bottom:
        return Offset(labelTopLeft.dx + labelSize.width * 0.5, labelTopLeft.dy);
      case LabelPlacement.bottomRight:
        return Offset(labelTopLeft.dx + labelSize.width * 0.8, labelTopLeft.dy);
      case LabelPlacement.left:
        return Offset(
          labelTopLeft.dx + labelSize.width,
          labelTopLeft.dy + labelSize.height * 0.3,
        );
      case LabelPlacement.right:
        return Offset(
          labelTopLeft.dx,
          labelTopLeft.dy + labelSize.height * 0.3,
        );
    }
  }
}

class _LabelLayout {
  static const double _collisionGap = 10;
  static const double _rowGap = 12;
  static const double _gapToNav = 14;

  static Map<GuideTarget, Offset> resolvePositions({
    required List<GuideItem> items,
    required Map<GuideTarget, Rect?> rects,
    required Map<GuideTarget, Size> labelSizes,
    required Size screenSize,
    required double headerHeight,
    required double footerHeight,
  }) {
    final positions = <GuideTarget, Offset>{};
    final sizes = <GuideTarget, Size>{};

    for (final item in items) {
      final rect = rects[item.target];
      if (rect == null) continue;
      final size = _LabelMetrics.estimatedSize(
        item.target,
        screenSize.width,
        labelSizes[item.target],
      );
      sizes[item.target] = size;
      positions[item.target] = _LabelGeometry.labelTopLeft(
        rect: rect,
        placement: item.placement,
        labelSize: size,
        screenSize: screenSize,
        headerHeight: headerHeight,
        footerHeight: footerHeight,
      );
    }

    final bottomItems = items
        .where((item) => _bottomNavTargets.contains(item.target))
        .toList();
    final bottomPositions = _layoutBottomNav(
      bottomItems: bottomItems,
      rects: rects,
      sizes: sizes,
      screenSize: screenSize,
      headerHeight: headerHeight,
      footerHeight: footerHeight,
    );
    positions.addAll(bottomPositions);

    final obstacles = <Rect>[
      for (final entry in bottomPositions.entries)
        Rect.fromLTWH(
          entry.value.dx,
          entry.value.dy,
          sizes[entry.key]?.width ?? 0,
          sizes[entry.key]?.height ?? 0,
        ),
    ];

    final nonBottomItems =
        items.where((item) => !_bottomNavTargets.contains(item.target)).toList()
          ..sort((a, b) {
            final posA = positions[a.target];
            final posB = positions[b.target];
            if (posA == null || posB == null) return 0;
            return posA.dy.compareTo(posB.dy);
          });

    for (final item in nonBottomItems) {
      final pos = positions[item.target];
      final size = sizes[item.target];
      if (pos == null || size == null) continue;
      var rect = Rect.fromLTWH(pos.dx, pos.dy, size.width, size.height);
      rect = _resolveOverlap(
        rect,
        obstacles,
        screenSize,
        headerHeight,
        footerHeight,
      );
      positions[item.target] = rect.topLeft;
      obstacles.add(rect);
    }

    return positions;
  }

  static Map<GuideTarget, Offset> _layoutBottomNav({
    required List<GuideItem> bottomItems,
    required Map<GuideTarget, Rect?> rects,
    required Map<GuideTarget, Size> sizes,
    required Size screenSize,
    required double headerHeight,
    required double footerHeight,
  }) {
    if (bottomItems.isEmpty) return {};

    final padding = screenSize.width > 600 ? 16.0 : 12.0;
    final bottomRects = <Rect>[];
    for (final item in bottomItems) {
      final rect = rects[item.target];
      if (rect != null) bottomRects.add(rect);
    }
    if (bottomRects.isEmpty) return {};

    final navTop = bottomRects
        .map((rect) => rect.top)
        .reduce((a, b) => a < b ? a : b);

    final verifySize = sizes[GuideTarget.navVerify];
    final historySize = sizes[GuideTarget.navHistory];
    final bookmarkSize = sizes[GuideTarget.navBookmark];

    final row2Height = math.max(
      historySize?.height ?? 0,
      bookmarkSize?.height ?? 0,
    );
    final row1Height = verifySize?.height ?? row2Height;

    final maxRow1Y = screenSize.height - footerHeight - row1Height;
    var row1Y = navTop - _gapToNav - row1Height;
    row1Y = row1Y.clamp(headerHeight, maxRow1Y).toDouble();

    var row2Y = row1Y - _rowGap - row2Height;
    if (row2Y < headerHeight) {
      final candidateBelow = row1Y + row1Height + _rowGap;
      final maxBelow = screenSize.height - footerHeight - row2Height;
      if (candidateBelow <= maxBelow) {
        row2Y = candidateBelow;
      } else {
        row2Y = headerHeight;
      }
    }

    final positions = <GuideTarget, Offset>{};
    if (historySize != null) {
      final x = padding;
      positions[GuideTarget.navHistory] = Offset(x, row2Y);
    }
    if (bookmarkSize != null) {
      final x = screenSize.width - padding - bookmarkSize.width;
      positions[GuideTarget.navBookmark] = Offset(x, row2Y);
    }
    if (verifySize != null) {
      final x = (screenSize.width - verifySize.width) / 2;
      positions[GuideTarget.navVerify] = Offset(
        x
            .clamp(padding, screenSize.width - padding - verifySize.width)
            .toDouble(),
        row1Y,
      );
    }

    return positions;
  }

  static Rect _resolveOverlap(
    Rect rect,
    List<Rect> obstacles,
    Size screenSize,
    double headerHeight,
    double footerHeight,
  ) {
    var candidate = rect;
    var guard = 0;
    while (_overlapsAny(candidate, obstacles) && guard < 8) {
      final overlap = obstacles.firstWhere(
        (other) => _overlaps(candidate, other),
      );
      final pushUpDy = (overlap.top - _collisionGap) - candidate.bottom;
      final pushDownDy = (overlap.bottom + _collisionGap) - candidate.top;

      final upCandidate = _clampRect(
        candidate.translate(0, pushUpDy),
        screenSize,
        headerHeight,
        footerHeight,
      );
      final downCandidate = _clampRect(
        candidate.translate(0, pushDownDy),
        screenSize,
        headerHeight,
        footerHeight,
      );

      final upValid = !_overlapsAny(upCandidate, obstacles);
      final downValid = !_overlapsAny(downCandidate, obstacles);

      if (upValid && downValid) {
        candidate = pushUpDy.abs() <= pushDownDy.abs()
            ? upCandidate
            : downCandidate;
      } else if (upValid) {
        candidate = upCandidate;
      } else if (downValid) {
        candidate = downCandidate;
      } else {
        final direction = candidate.center.dx < screenSize.width / 2 ? -1 : 1;
        candidate = candidate.translate(
          direction * (candidate.width * 0.25),
          0,
        );
        candidate = _clampRect(
          candidate,
          screenSize,
          headerHeight,
          footerHeight,
        );
      }

      guard++;
    }
    return candidate;
  }

  static bool _overlapsAny(Rect rect, List<Rect> others) {
    for (final other in others) {
      if (_overlaps(rect, other)) {
        return true;
      }
    }
    return false;
  }

  static bool _overlaps(Rect a, Rect b) {
    return a.inflate(_collisionGap).overlaps(b.inflate(_collisionGap));
  }

  static Rect _clampRect(
    Rect rect,
    Size screenSize,
    double headerHeight,
    double footerHeight,
  ) {
    final padding = screenSize.width > 600 ? 16.0 : 12.0;
    final minX = padding;
    final maxX = screenSize.width - padding - rect.width;
    final minY = headerHeight;
    final maxY = screenSize.height - footerHeight - rect.height;

    final boundMaxX = maxX < minX ? minX : maxX;
    final boundMaxY = maxY < minY ? minY : maxY;

    final clampedX = rect.left.clamp(minX, boundMaxX).toDouble();
    final clampedY = rect.top.clamp(minY, boundMaxY).toDouble();
    return Rect.fromLTWH(clampedX, clampedY, rect.width, rect.height);
  }
}

/// 코치 페인터 - 배경, 하이라이트, 연결선
class _CoachPainter extends CustomPainter {
  final List<GuideItem> items;
  final Map<GuideTarget, Rect?> rects;
  final Map<GuideTarget, Size> labelSizes;
  final Map<GuideTarget, Offset> labelPositions;
  final bool isDark;
  final double headerHeight;
  final double footerHeight;
  final double safeAreaBottom;

  _CoachPainter({
    required this.items,
    required this.rects,
    required this.labelSizes,
    required this.labelPositions,
    required this.isDark,
    required this.headerHeight,
    required this.footerHeight,
    required this.safeAreaBottom,
  });

  @override
  void paint(Canvas canvas, Size size) {
    // 배경 스크림
    final scrimColor = isDark
        ? const Color(0xFF2A2A2A).withOpacity( 0.78)
        : const Color(0xFFCCCCCC).withOpacity( 0.78);

    // Paint 객체들
    final dashPaint = Paint()
      ..style = PaintingStyle.stroke
      ..strokeWidth = 2.4
      ..color = _HelpBrand.blueLight.withOpacity( 0.95)
      ..strokeCap = StrokeCap.round;

    final Path full = Path()..addRect(Offset.zero & size);
    final Path holes = Path();

    // 모든 아이템 그리기 - 첫 번째 루프 (holes 생성)
    for (final item in items) {
      final rect = rects[item.target];
      if (rect == null) continue;

      // 하이라이트 영역 (bottomnav는 뭉뚝한 사각형)
      final isBottomNav =
          item.target == GuideTarget.navHistory ||
          item.target == GuideTarget.navVerify ||
          item.target == GuideTarget.navBookmark;

      final radius = isBottomNav
          ? const Radius.circular(4)
          : const Radius.circular(24);

      final inflateValue = isBottomNav ? 16.0 : 6.0;
      final topInflate = isBottomNav ? 0.0 : 6.0; // bottomnav는 위쪽 확장 없음
      final bottomInflate = isBottomNav ? 7.0 : 6.0;

      final highlight = RRect.fromRectAndRadius(
        Rect.fromLTRB(
          rect.left - inflateValue,
          rect.top - topInflate,
          rect.right + inflateValue,
          rect.bottom + bottomInflate,
        ),
        radius,
      );

      holes.addRRect(highlight);
    }

    final overlay = Path.combine(PathOperation.difference, full, holes);
    canvas.drawPath(overlay, Paint()..color = scrimColor);

    // 두 번째 루프 - 점선 및 연결선 그리기
    for (final item in items) {
      final rect = rects[item.target];
      if (rect == null) continue;

      // bottomnav는 뭉뚝한 사각형
      final isBottomNav =
          item.target == GuideTarget.navHistory ||
          item.target == GuideTarget.navVerify ||
          item.target == GuideTarget.navBookmark;

      final hideConnector =
          isBottomNav ||
          item.target == GuideTarget.settings ||
          item.target == GuideTarget.verifyStartButton ||
          item.target == GuideTarget.inputField ||
          item.target == GuideTarget.inputTypeSelector;

      final radius = isBottomNav
          ? const Radius.circular(4)
          : const Radius.circular(24);

      final inflateValue = isBottomNav ? 16.0 : 6.0;
      final topInflate = isBottomNav ? 0.0 : 6.0; // bottomnav는 위쪽 확장 없음
      final bottomInflate = isBottomNav ? 7.0 : 6.0;

      final highlight = RRect.fromRectAndRadius(
        Rect.fromLTRB(
          rect.left - inflateValue,
          rect.top - topInflate,
          rect.right + inflateValue,
          rect.bottom + bottomInflate,
        ),
        radius,
      );

      // 점선 테두리
      _drawDashedRRect(canvas, highlight, dashPaint, dash: 6, gap: 7);

      if (!hideConnector) {
        // 라벨로 연결선 (간단한 고정 크기 사용)
        final labelSize = _LabelMetrics.estimatedSize(
          item.target,
          size.width,
          labelSizes[item.target],
        );
        final labelTopLeft =
            labelPositions[item.target] ??
            _LabelGeometry.labelTopLeft(
              rect: rect,
              placement: item.placement,
              labelSize: labelSize,
              screenSize: size,
              headerHeight: headerHeight,
              footerHeight: footerHeight,
            );
        final labelAnchor = _LabelGeometry.labelAnchor(
          labelTopLeft: labelTopLeft,
          labelSize: labelSize,
          placement: item.placement,
        );

        final targetAnchor = _targetAnchor(rect, item.placement);

        final path = Path();
        path.moveTo(targetAnchor.dx, targetAnchor.dy);

        final mid = Offset(
          (targetAnchor.dx + labelAnchor.dx) / 2,
          (targetAnchor.dy + labelAnchor.dy) / 2,
        );
        final ctrl = _controlPoint(mid, targetAnchor, labelAnchor);

        path.quadraticBezierTo(
          ctrl.dx,
          ctrl.dy,
          labelAnchor.dx,
          labelAnchor.dy,
        );

        _drawDashedPath(canvas, path, dashPaint, dash: 6, gap: 7);

        // 시작점 표시
        canvas.drawCircle(
          targetAnchor,
          4.0,
          Paint()..color = _HelpBrand.blueLight.withOpacity( 0.95),
        );
      }
    }
  }

  Offset _targetAnchor(Rect r, LabelPlacement placement) {
    const offset = 10.0;
    switch (placement) {
      case LabelPlacement.topLeft:
      case LabelPlacement.top:
      case LabelPlacement.topRight:
        return Offset(r.center.dx, r.top - offset);
      case LabelPlacement.bottomLeft:
      case LabelPlacement.bottom:
      case LabelPlacement.bottomRight:
        return Offset(r.center.dx, r.bottom + offset);
      case LabelPlacement.left:
        return Offset(r.left - offset, r.center.dy);
      case LabelPlacement.right:
        return Offset(r.right + offset, r.center.dy);
    }
  }

  Offset _controlPoint(Offset mid, Offset a, Offset b) {
    final dx = b.dx - a.dx;
    final dy = b.dy - a.dy;

    // 곡선 강도
    const curveFactor = 50.0;

    if (dx.abs() > dy.abs()) {
      return Offset(
        mid.dx,
        mid.dy - curveFactor * (dy.sign == 0 ? 1 : dy.sign),
      );
    } else {
      return Offset(
        mid.dx + curveFactor * (dx.sign == 0 ? 1 : dx.sign),
        mid.dy,
      );
    }
  }

  void _drawDashedRRect(
    Canvas canvas,
    RRect rrect,
    Paint paint, {
    required double dash,
    required double gap,
  }) {
    final path = Path()..addRRect(rrect);
    _drawDashedPath(canvas, path, paint, dash: dash, gap: gap);
  }

  void _drawDashedPath(
    Canvas canvas,
    Path path,
    Paint paint, {
    required double dash,
    required double gap,
  }) {
    final metrics = path.computeMetrics(forceClosed: false);
    for (final metric in metrics) {
      double distance = 0.0;
      while (distance < metric.length) {
        final len = (distance + dash < metric.length)
            ? dash
            : metric.length - distance;
        final extract = metric.extractPath(distance, distance + len);
        canvas.drawPath(extract, paint);
        distance += dash + gap;
      }
    }
  }

  @override
  bool shouldRepaint(covariant _CoachPainter oldDelegate) {
    if (oldDelegate.items.length != items.length) return true;
    for (final item in items) {
      if (oldDelegate.rects[item.target] != rects[item.target]) return true;
    }
    if (oldDelegate.labelSizes.length != labelSizes.length) return true;
    for (final entry in labelSizes.entries) {
      final prev = oldDelegate.labelSizes[entry.key];
      if (prev == null || prev != entry.value) return true;
    }
    if (oldDelegate.labelPositions.length != labelPositions.length) return true;
    for (final entry in labelPositions.entries) {
      final prev = oldDelegate.labelPositions[entry.key];
      if (prev == null || prev != entry.value) return true;
    }
    return oldDelegate.isDark != isDark ||
        oldDelegate.headerHeight != headerHeight ||
        oldDelegate.footerHeight != footerHeight ||
        oldDelegate.safeAreaBottom != safeAreaBottom;
  }
}
