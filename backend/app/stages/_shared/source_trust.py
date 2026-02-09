from __future__ import annotations

import json
from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit

_TIER_SCORES: dict[str, float] = {
    "government": 0.96,
    "public_org": 0.90,
    "major_news": 0.80,
    "specialized_news": 0.72,
    "platform": 0.45,
    "encyclopedia": 0.82,
    "unknown": 0.55,
}

_MAJOR_NEWS_DOMAINS: tuple[str, ...] = (
    "yna.co.kr",
    "newsis.com",
    "kbs.co.kr",
    "mbc.co.kr",
    "sbs.co.kr",
    "ytn.co.kr",
    "chosun.com",
    "joongang.co.kr",
    "donga.com",
    "hani.co.kr",
    "khan.co.kr",
    "mk.co.kr",
    "hankyung.com",
    "moneytoday.co.kr",
    "seoul.co.kr",
    "ohmynews.com",
    "edaily.co.kr",
)

_SPECIALIZED_NEWS_DOMAINS: tuple[str, ...] = (
    "zdnet.co.kr",
    "itworld.co.kr",
    "bloter.net",
    "ddaily.co.kr",
)

_PLATFORM_DOMAINS: tuple[str, ...] = (
    "blog.naver.com",
    "tistory.com",
    "medium.com",
    "brunch.co.kr",
    "velog.io",
    "youtube.com",
    "youtu.be",
    "dcinside.com",
    "mlbpark.com",
)

_PUBLIC_ORG_DOMAINS: tuple[str, ...] = (
    "or.kr",
    "ac.kr",
    "re.kr",
)


def extract_domain(url: str) -> str:
    netloc = (urlsplit(str(url or "").strip()).netloc or "").lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def _domain_matches(domain: str, patterns: tuple[str, ...]) -> bool:
    if not domain:
        return False
    return any(domain == pattern or domain.endswith(f".{pattern}") for pattern in patterns)


@lru_cache(maxsize=16)
def _parse_overrides(raw: str) -> dict[str, str]:
    text = str(raw or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    overrides: dict[str, str] = {}
    for key, value in parsed.items():
        domain = str(key or "").strip().lower()
        tier = str(value or "").strip().lower()
        if not domain or tier not in _TIER_SCORES:
            continue
        if domain.startswith("www."):
            domain = domain[4:]
        overrides[domain] = tier
    return overrides


def _lookup_override(domain: str, overrides: dict[str, str]) -> str | None:
    if not domain or not overrides:
        return None
    if domain in overrides:
        return overrides[domain]
    for key, tier in overrides.items():
        if domain.endswith(f".{key}"):
            return tier
    return None


def resolve_source_tier(
    *,
    url: str,
    source_type: str,
    overrides_json: str = "",
) -> tuple[str, str]:
    domain = extract_domain(url)
    source = str(source_type or "").upper()
    overrides = _parse_overrides(overrides_json)

    override_tier = _lookup_override(domain, overrides)
    if override_tier:
        return domain, override_tier

    if source in {"WIKIPEDIA", "KNOWLEDGE_BASE", "KB_DOC"}:
        return domain or "wiki", "encyclopedia"
    if domain.endswith(".go.kr") or domain == "korea.kr":
        return domain, "government"
    if _domain_matches(domain, _MAJOR_NEWS_DOMAINS):
        return domain, "major_news"
    if _domain_matches(domain, _SPECIALIZED_NEWS_DOMAINS):
        return domain, "specialized_news"
    if _domain_matches(domain, _PLATFORM_DOMAINS):
        return domain, "platform"
    if _domain_matches(domain, _PUBLIC_ORG_DOMAINS):
        return domain, "public_org"

    if source == "NEWS":
        return domain, "specialized_news"
    if source in {"WEB_URL", "WEB"}:
        return domain, "unknown"

    return domain, "unknown"


def source_tier_score(tier: str) -> float:
    return float(_TIER_SCORES.get(str(tier or "").strip().lower(), _TIER_SCORES["unknown"]))


def build_source_trust(
    *,
    url: str,
    source_type: str,
    overrides_json: str = "",
) -> dict[str, Any]:
    domain, tier = resolve_source_tier(url=url, source_type=source_type, overrides_json=overrides_json)
    score = source_tier_score(tier)
    return {
        "source_domain": domain or "unknown",
        "source_tier": tier,
        "source_trust_score": round(float(score), 4),
    }

