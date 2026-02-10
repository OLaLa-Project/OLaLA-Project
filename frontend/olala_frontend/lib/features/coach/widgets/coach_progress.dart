part of 'coach_overlay.dart';

class _CoachDimPainter extends CustomPainter {
  final Rect hole;
  final double holeRadius;
  final bool useRounded;
  final Color dimColor;

  _CoachDimPainter({
    required this.hole,
    required this.holeRadius,
    required this.useRounded,
    required this.dimColor,
  });

  @override
  void paint(Canvas canvas, Size size) {
    final full = Path()..addRect(Offset.zero & size);
    final Path cutout = useRounded
        ? (Path()
          ..addRRect(
            RRect.fromRectAndRadius(
              hole,
              Radius.circular(holeRadius),
            ),
          ))
        : (Path()..addRect(hole));

    final overlay = Path.combine(PathOperation.difference, full, cutout);
    canvas.drawPath(overlay, Paint()..color = dimColor);
  }

  @override
  bool shouldRepaint(covariant _CoachDimPainter oldDelegate) {
    return oldDelegate.hole != hole ||
        oldDelegate.holeRadius != holeRadius ||
        oldDelegate.useRounded != useRounded ||
        oldDelegate.dimColor != dimColor;
  }
}
