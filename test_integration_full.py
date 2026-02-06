
import requests
import json
import sys

URL = "http://localhost:8080/api/truth/check/stream"
PAYLOAD = {
    "input_payload": "https://snsmatch.com/news.php?news_no=172047",
    "input_type": "url"
}

def test_integration():
    print(f"Connecting to Backend at {URL}...")
    try:
        with requests.post(URL, json=PAYLOAD, stream=True, timeout=120) as r:
            print(f"Status Code: {r.status_code}")
            if r.status_code != 200:
                print(f"Error: {r.text}")
                return

            print("Stream started. Listening for events...")
            for line in r.iter_lines():
                if line:
                    decoded = line.decode('utf-8')
                    try:
                        data = json.loads(decoded)
                        print(f"[RECV] Event: {data.get('event', 'unknown')} | Data keys: {list(data.get('data', {}).keys())}")
                        # print(decoded) # Uncomment for full debug
                    except json.JSONDecodeError:
                        print(f"[RECV] Raw: {decoded}")
    except requests.exceptions.RequestException as e:
        print(f"Connection Failed: {e}")

if __name__ == "__main__":
    test_integration()
