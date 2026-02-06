import json
import re
from app.stages._shared.guardrails import parse_json_safe

# Logged failing JSON snippet (reconstructed based on logs)
# The error "Expecting ',' delimiter" suggests missing commas between list items or fields.
malformed_json_1 = """
{
  "stance": "TRUE",
  "confidence": 0.95,
  "reasoning_bullets": [
    "bullet 1",
    "bullet 2"
  ],
  "citations": [
    {
      "evid_id": "ev_ffd90ce5",
      "url": "http://example.com/1",
      "quote": "quote 1",
      "title": "title 1"
    }  
    {
      "evid_id": "ev_a154e17a",
      "url": "http://example.com/2",
      "quote": "quote 2",
      "title": "title 2"
    }
  ]
}
"""

# Another potential case from logs: unescaped quotes or cut off
malformed_json_2 = """
{
  "stance": "MIXED",
  "citations": [
    {
      "title": "GPT'야 코딩해줘 오픈AI, 코딩 모델 'GPT-5.3-코덱스' 출시"
    }
  ]
}
"""

malformed_json_3 = """
{
    "title": "This is a "bad" title",
    "other": "value"
}
"""

malformed_json_4 = """
{
  "citations": [
    {
      "title": "Title 1"
    },
    {
      "title": "Title 2"
    },
    {
"""

def test_parsing():
    print("Testing Malformed JSON 1 (Missing Comma in List):")
    try:
        result = parse_json_safe(malformed_json_1)
        print("Success:", json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print("Failed:", e)

    print("\nTesting Malformed JSON 2 (Quotes):")
    try:
        result = parse_json_safe(malformed_json_2)
        print("Success:", json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print("Failed:", e)
        
    print("\nTesting Malformed JSON 3 (Unescaped Quotes):")
    try:
        result = parse_json_safe(malformed_json_3)
        print("Success:", json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print("Failed:", e)

    print("\nTesting Malformed JSON 4 (Truncated List):")
    try:
        result = parse_json_safe(malformed_json_4)
        print("Success:", json.dumps(result, indent=2, ensure_ascii=False))
    except Exception as e:
        print("Failed:", e)



if __name__ == "__main__":
    test_parsing()
