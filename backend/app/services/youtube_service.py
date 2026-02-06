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
    @staticmethod
    def clean_transcript(text: str) -> str:
        """자막 텍스트 정제 (규칙 기반)."""
        if not text:
            return ""

        # 1. 문장부호 및 불필요한 기호 정리
        # '>>'는 화자 전환을 의미하는 경우가 많으나, 너무 많으면 가독성 해침 -> 줄바꿈으로 변경하여 문리 분리 유도
        cleaned = text.replace(">>", " ").replace("&nbsp;", " ")

        # 2. 반복되는 단어/구문 축약 (예: "네 네 네" -> "네")
        # 동일 단어가 공백으로 구분되어 2회 이상 반복될 때 하나로.
        # \b(\w+) 은 한글 단어도 매칭됨.
        cleaned = re.sub(r'\b(\w+)(?:\s+\1\b)+', r'\1', cleaned)

        # 3. 추임새/필러 제거 (보수적 접근)
        # 문장 시작 부분의 "네.", "아.", "음.", "그," 등을 제거
        fillers = r'(?:네|아|음|어|그|저|뭐|이제|약간|그냥|진짜|사실|그래서)'

        # 텍스트를 문장 단위(마침표 등)로 나누어 처리하거나,
        # 전체 텍스트에서 패턴 매칭. 여기서는 간단히 re.sub 사용.
        # 문장 시작(Start of string) 또는 문장 부호 뒤(.?!) 공백 후

        # 패턴: (문장시작|종결부호공백) + (필러) + (선택적 구두점) + (공백)
        # 반복적으로 제거하기 위해 loop 사용이 어려우니 regex로 처리
        # 예: "네. 아. 그렇군요" -> "그렇군요"

        # 전략: 먼저 텍스트를 더 잘게 쪼갠 후 다시 합치는 방식 사용
        # 여기서는 간단한 전처리만 수행

        # "네." "아," 처럼 독립적으로 쓰인 필러 제거
        cleaned = re.sub(fr'(?<=[\s.?!])({fillers})[.,]?\s+', '', cleaned)
        cleaned = re.sub(fr'^{fillers}[.,]?\s+', '', cleaned)

        # 4. 공백 정리
        cleaned = re.sub(r'\s+', ' ', cleaned).strip()

        return cleaned