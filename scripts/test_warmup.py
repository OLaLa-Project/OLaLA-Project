"""
Quick test to verify model warm-up is working.
"""
import requests
import time

backend_url = "http://localhost:8080"

print("Testing backend health...")
response = requests.get(f"{backend_url}/api/health")
print(f"Health check: {response.status_code}")
print(response.json())

print("\nTesting quick RAG query (should be fast if models are warmed up)...")
start = time.time()

# Simple test query
test_payload = {
    "request": "세종대왕은 누구인가요?",
    "mode": "fast"
}

response = requests.post(
    f"{backend_url}/api/truth/check/stream",
    json=test_payload,
    stream=True,
    timeout=30
)

elapsed = time.time() - start
print(f"First response time: {elapsed:.2f}s")
print(f"Status: {response.status_code}")

if elapsed < 5:
    print("✅ Models appear to be pre-warmed (fast response)")
else:
    print("⚠️  Slow response - models may not be pre-loaded")
