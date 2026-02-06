
import sys
import logging
# Add backend directory to path to import service
sys.path.append('/home/user/frontback/backend')

from app.services.youtube_service import YoutubeService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_youtube_fetch():
    # Known video: "이혜훈, 차입 정치자금으로 차량 구매 의혹" 
    # Video ID: bosK2EKes3U
    test_url = "https://www.youtube.com/watch?v=YTv8xPurZfk"
    
    print(f"Testing URL: {test_url}")
    
    video_id = YoutubeService.extract_video_id(test_url)
    print(f"Extracted Video ID: {video_id}")
    
    if not video_id:
        print("FAIL: Could not extract video ID")
        return

    print("Fetching transcript...")
    transcript = YoutubeService.get_transcript(video_id)
    
    if transcript:
        print("\n[SUCCESS] Transcript fetched!")
        print(f"Length: {len(transcript)} chars")
        print("Raw Preview (first 200 chars):")
        print("-" * 50)
        print(transcript[:200])
        print("-" * 50)

        cleaned = YoutubeService.clean_transcript(transcript)
        print("\n[SUCCESS] Transcript Cleaned!")
        print(f"Cleaned Length: {len(cleaned)} chars")
        print("Cleaned Preview (first 200 chars):")
        print("-" * 50)
        print(cleaned[:200])
        print("-" * 50)
    else:
        print("\n[FAIL] Transcript not found or disabled.")

if __name__ == "__main__":
    test_youtube_fetch()
