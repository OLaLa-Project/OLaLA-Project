import html as html_lib
import logging
import re
from typing import Dict, Any

from app.services.youtube_service import YoutubeService

logger = logging.getLogger(__name__)


def fetch_url_content(url: str) -> Dict[str, str]:
    """
    URL에서 기사 본문과 제목 추출 (trafilatura 사용).
    trafilatura가 없으면 빈 결과 반환.
    """
    try:
        import trafilatura
    except ImportError:
        logger.warning("trafilatura 미설치 - URL 콘텐츠 추출 불가")
        return {"text": "", "title": ""}

    try:
        downloaded = trafilatura.fetch_url(url)
        if not downloaded:
            return {"text": "", "title": ""}

        result = trafilatura.bare_extraction(
            downloaded, include_comments=False, include_tables=False
        )
        if result:
            text = getattr(result, "text", "") or (
                result.get("text", "") if isinstance(result, dict) else ""
            )
            title = getattr(result, "title", "") or (
                result.get("title", "") if isinstance(result, dict) else ""
            )

            # Fallback: extract title from HTML meta/title tags
            if not title and downloaded:
                og_match = re.search(
                    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)["\']',
                    downloaded,
                    re.IGNORECASE,
                )
                if og_match:
                    title = og_match.group(1).strip()
                if not title:
                    meta_match = re.search(
                        r'<meta[^>]+name=["\']title["\'][^>]+content=["\']([^"\']+)["\']',
                        downloaded,
                        re.IGNORECASE,
                    )
                    if meta_match:
                        title = meta_match.group(1).strip()
                if not title:
                    title_match = re.search(
                        r"<title[^>]*>(.*?)</title>",
                        downloaded,
                        re.IGNORECASE | re.DOTALL,
                    )
                    if title_match:
                        title = re.sub(r"\s+", " ", title_match.group(1)).strip()
                if title:
                    title = html_lib.unescape(title)

            return {"text": text, "title": title}
    except Exception as e:
        logger.warning(f"URL 콘텐츠 추출 실패 ({url}): {e}")

    return {"text": "", "title": ""}


def prefetch_url(
    url: str,
    *,
    max_chars: int = 8000,
    allow_youtube: bool = True,
) -> Dict[str, Any]:
    """
    URL 선처리: 유튜브는 자막, 일반 URL은 기사 본문을 반환.
    """
    if not url:
        return {"text": "", "title": "", "source_type": "article", "url": url}

    video_id = YoutubeService.extract_video_id(url) if allow_youtube else None
    if video_id:
        transcript = YoutubeService.get_transcript(video_id)
        if transcript:
            cleaned = YoutubeService.clean_transcript(transcript)
            if max_chars > 0:
                cleaned = cleaned[:max_chars]
            title_data = fetch_url_content(url)
            title = title_data.get("title", "")
            logger.info(
                "YouTube transcript fetched: %s chars (video_id=%s)",
                len(cleaned),
                video_id,
            )
            return {
                "text": cleaned,
                "title": title,
                "source_type": "youtube",
                "url": url,
            }
        logger.warning("YouTube transcript missing: %s", video_id)
        title_data = fetch_url_content(url)
        return {
            "text": "",
            "title": title_data.get("title", ""),
            "source_type": "youtube",
            "url": url,
        }

    fetched = fetch_url_content(url)
    return {
        "text": fetched.get("text", ""),
        "title": fetched.get("title", ""),
        "source_type": "article",
        "url": url,
    }
