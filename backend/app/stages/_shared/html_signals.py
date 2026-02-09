from __future__ import annotations

import re
from typing import Any

import requests

_REF_LINK_PATTERNS: tuple[str, ...] = (
    "go.kr",
    "korea.kr",
    "fss.or.kr",
    "kostat.go.kr",
    "index.go.kr",
    "law.go.kr",
    "scourt.go.kr",
    "moef.go.kr",
    "bok.or.kr",
    "dart.fss.or.kr",
)

_ANONYMOUS_TERMS: tuple[str, ...] = (
    "관계자",
    "익명",
    "지인",
    "커뮤니티",
    "카더라",
    "알려졌다",
    "전해졌다",
)

_CLICKBAIT_TERMS: tuple[str, ...] = (
    "충격",
    "긴급",
    "단독",
    "경악",
    "대박",
    "실화",
    "역대급",
)


def _strip_html(value: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", value, flags=re.IGNORECASE)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _safe_ratio(numer: float, denom: float) -> float:
    if denom <= 0:
        return 0.0
    return max(0.0, min(1.0, float(numer) / float(denom)))


def _extract_links(html: str) -> list[str]:
    return re.findall(r'href=["\']([^"\']+)["\']', html, flags=re.IGNORECASE)


def _contains_any(text: str, terms: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _clip(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _neutral_result(fetch_ok: bool = False) -> dict[str, Any]:
    return {
        "fetch_ok": fetch_ok,
        "byline_present": False,
        "date_present": False,
        "correction_notice_present": False,
        "reference_link_count": 0,
        "reference_link_quality_score": 0.0,
        "anonymous_source_ratio": 0.0,
        "clickbait_pattern": False,
        "html_signal_score": 0.5,
        "breakdown": {
            "base": 0.5,
            "byline_bonus": 0.0,
            "date_bonus": 0.0,
            "correction_bonus": 0.0,
            "reference_bonus": 0.0,
            "anonymous_penalty": 0.0,
            "clickbait_penalty": 0.0,
        },
    }


def analyze_html_signals(
    *,
    url: str,
    title: str,
    snippet: str,
    timeout_seconds: float = 3.0,
) -> dict[str, Any]:
    if not url:
        return _neutral_result(fetch_ok=False)

    try:
        response = requests.get(
            url,
            timeout=max(0.5, float(timeout_seconds)),
            headers={"User-Agent": "Mozilla/5.0 (OLaLA/1.0; +https://local)"},
        )
        if response.status_code >= 400:
            return _neutral_result(fetch_ok=False)
        html = str(response.text or "")
        if not html:
            return _neutral_result(fetch_ok=False)
    except Exception:
        return _neutral_result(fetch_ok=False)

    plain = _strip_html(html)
    title_text = str(title or "")
    snippet_text = str(snippet or "")

    byline_present = bool(
        re.search(r'<meta[^>]+name=["\']author["\']', html, flags=re.IGNORECASE)
        or re.search(r'<meta[^>]+property=["\']article:author["\']', html, flags=re.IGNORECASE)
        or re.search(r'author["\']?\s*[:=]', html, flags=re.IGNORECASE)
        or re.search(r"기자", plain)
        or re.search(r"\bbyline\b", html, flags=re.IGNORECASE)
    )
    date_present = bool(
        re.search(r'published[_\- ]?time', html, flags=re.IGNORECASE)
        or re.search(r'modified[_\- ]?time', html, flags=re.IGNORECASE)
        or re.search(r"\b\d{4}[./-]\d{1,2}[./-]\d{1,2}\b", plain)
        or re.search(r"<time[^>]*datetime=", html, flags=re.IGNORECASE)
    )
    correction_present = bool(
        re.search(r"정정|바로잡|수정 공지|correction|corrected", plain, flags=re.IGNORECASE)
    )

    links = _extract_links(html)
    reference_link_count = len(links)
    high_quality_refs = sum(
        1 for link in links if _contains_any(link, _REF_LINK_PATTERNS)
    )
    reference_quality = _clip(_safe_ratio(high_quality_refs, max(1, reference_link_count)) * 0.7 + _safe_ratio(reference_link_count, 8) * 0.3)

    anonymous_hits = sum(plain.count(term) for term in _ANONYMOUS_TERMS)
    quote_like_hits = len(re.findall(r"(“|\"|라고|밝혔|말했|전했)", plain))
    anonymous_ratio = _clip(_safe_ratio(anonymous_hits, max(1, quote_like_hits)))

    title_clickbait = _contains_any(title_text, _CLICKBAIT_TERMS)
    evidence_thin = reference_link_count == 0 and len(snippet_text) < 160
    clickbait_pattern = bool(title_clickbait and evidence_thin)

    base = 0.5
    byline_bonus = 0.08 if byline_present else 0.0
    date_bonus = 0.08 if date_present else 0.0
    correction_bonus = 0.06 if correction_present else 0.0
    reference_bonus = 0.20 * reference_quality
    anonymous_penalty = 0.14 * anonymous_ratio
    clickbait_penalty = 0.12 if clickbait_pattern else 0.0

    signal_score = _clip(
        base
        + byline_bonus
        + date_bonus
        + correction_bonus
        + reference_bonus
        - anonymous_penalty
        - clickbait_penalty
    )

    return {
        "fetch_ok": True,
        "byline_present": byline_present,
        "date_present": date_present,
        "correction_notice_present": correction_present,
        "reference_link_count": reference_link_count,
        "reference_link_quality_score": round(reference_quality, 4),
        "anonymous_source_ratio": round(anonymous_ratio, 4),
        "clickbait_pattern": clickbait_pattern,
        "html_signal_score": round(signal_score, 4),
        "breakdown": {
            "base": round(base, 4),
            "byline_bonus": round(byline_bonus, 4),
            "date_bonus": round(date_bonus, 4),
            "correction_bonus": round(correction_bonus, 4),
            "reference_bonus": round(reference_bonus, 4),
            "anonymous_penalty": round(anonymous_penalty, 4),
            "clickbait_penalty": round(clickbait_penalty, 4),
        },
    }
