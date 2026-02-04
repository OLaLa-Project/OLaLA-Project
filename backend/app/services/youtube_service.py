import re
import logging
from typing import Optional
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound

logger = logging.getLogger(__name__)

class YoutubeService:
    """YouTube 자막 추출 서비스."""

    @staticmethod
    def extract_video_id(url: str) -> Optional[str]:
        """URL에서 YouTube Video ID 추출."""
        # 다양한 유튜브 URL 패턴 대응
        patterns = [
            r'(?:v=|\/)([0-9A-Za-z_-]{11}).*',
            r'(?:youtu\.be\/)([0-9A-Za-z_-]{11})',
            r'(?:embed\/)([0-9A-Za-z_-]{11})'
        ]
        
        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)
        return None

    @staticmethod
    def get_transcript(video_id: str) -> Optional[str]:
        """Video ID로 자막을 가져와서 하나의 텍스트로 병합."""
        try:
            # API 인스턴스 생성 (최신 버전 대응)
            ytt = YouTubeTranscriptApi()
            
            # 자막 목록 조회
            transcript_list = ytt.list(video_id)
            
            # 한국어 우선, 없으면 영어 (find_transcript는 실패 시 NoTranscriptFound 발생)
            transcript = transcript_list.find_transcript(['ko', 'en'])
            
            # 실제 데이터 가져오기 (List[Dict])
            fetched_data = transcript.fetch()
            
            # 텍스트만 추출하여 병합
            full_text = " ".join([entry.text for entry in fetched_data])
            
            # 공백 정리
            full_text = " ".join(full_text.split())
            
            logger.info(f"YouTube Transcript fetched for {video_id}: {len(full_text)} chars")
            return full_text

        except (TranscriptsDisabled, NoTranscriptFound):
            logger.warning(f"No transcript found for video {video_id}")
            return None
        except Exception as e:
            logger.error(f"Failed to fetch transcript for {video_id}: {e}")
            return None
