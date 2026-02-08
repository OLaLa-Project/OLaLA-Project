import 'package:flutter/material.dart';
import '../../models/evidence_card.dart';

class EvidenceCardView extends StatelessWidget {
  final EvidenceCard card;

  const EvidenceCardView({super.key, required this.card});

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isDark = theme.brightness == Brightness.dark;
    final title = (card.title ?? '').trim();
    final source = (card.source ?? '').trim();
    final snippet = (card.snippet ?? '').trim();
    final url = (card.url ?? '').trim();

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 14),
      decoration: BoxDecoration(
        color: isDark ? theme.colorScheme.surface : Colors.white,
        borderRadius: BorderRadius.circular(16),
        border: Border.all(
          color: isDark
              ? theme.colorScheme.outlineVariant.withValues(alpha: 0.7)
              : const Color(0xFFE6ECFF),
        ),
        boxShadow: isDark
            ? const []
            : [
                BoxShadow(
                  color: Colors.black.withOpacity(0.03),
                  blurRadius: 14,
                  offset: const Offset(0, 8),
                ),
              ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (source.isNotEmpty)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
              decoration: BoxDecoration(
                color: isDark
                    ? const Color(0xFF3478F6).withValues(alpha: 0.2)
                    : const Color(0xFFE9F3FF),
                borderRadius: BorderRadius.circular(999),
              ),
              child: Text(
                source,
                style: const TextStyle(
                  color: Color(0xFF3478F6),
                  fontWeight: FontWeight.w900,
                  fontSize: 12,
                ),
              ),
            ),
          if (source.isNotEmpty) const SizedBox(height: 10),

          Text(
            title.isNotEmpty ? title : '근거 제목',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w900,
              color: isDark
                  ? theme.colorScheme.onSurface
                  : const Color(0xFF111827),
              height: 1.2,
            ),
          ),
          const SizedBox(height: 8),

          Text(
            snippet.isNotEmpty ? snippet : '근거 요약/인용문을 표시합니다.',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: isDark
                  ? theme.colorScheme.onSurfaceVariant
                  : const Color(0xFF374151),
              height: 1.45,
              fontWeight: FontWeight.w600,
            ),
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
          ),

          const SizedBox(height: 12),

          Row(
            children: [
              Icon(
                Icons.link_rounded,
                size: 18,
                color: isDark
                    ? theme.colorScheme.onSurfaceVariant
                    : const Color(0xFF6B7280),
              ),
              const SizedBox(width: 6),
              Expanded(
                child: Text(
                  url.isNotEmpty ? url : '출처 링크',
                  style: TextStyle(
                    color: isDark
                        ? theme.colorScheme.onSurfaceVariant
                        : const Color(0xFF6B7280),
                    fontWeight: FontWeight.w700,
                    fontSize: 12,
                  ),
                  maxLines: 1,
                  overflow: TextOverflow.ellipsis,
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}
