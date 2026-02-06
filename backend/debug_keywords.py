import sys
import os

# Add backend directory to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from app.services.wiki_query_normalizer import normalize_question_to_query
from app.services.wiki_usecase import extract_keywords

def test_keywords(text):
    print(f"--- Input: '{text}' ---")
    normalized = normalize_question_to_query(text)
    print(f"Normalized: '{normalized}'")
    keywords = extract_keywords(normalized)
    print(f"Keywords: {keywords}")
    print("-" * 30)

if __name__ == "__main__":
    test_keywords("윤석열 탄핵")
    test_keywords("윤석열 대통령 탄핵")
    test_keywords("탄핵 소추안")
    test_keywords("이재명 피습")
