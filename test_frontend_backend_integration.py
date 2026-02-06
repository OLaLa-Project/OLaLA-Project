#!/usr/bin/env python3
"""
Frontend-Backend 연동 테스트: 실시간 스트리밍 검증
네이버 뉴스 URL을 입력으로 하여 Stage 1~9까지 실행 확인
"""

import requests
import json
import sys

# 테스트할 URL
TEST_URL = "https://n.news.naver.com/mnews/article/448/0000588423"
BACKEND_URL = "http://localhost:8080"

def test_streaming_verification():
    """스트리밍 엔드포인트 테스트"""
    print("=" * 60)
    print("📡 실시간 스트리밍 검증 테스트")
    print("=" * 60)
    print(f"테스트 URL: {TEST_URL}")
    print(f"Backend: {BACKEND_URL}/api/truth/check/stream")
    print()
    
    payload = {
        "input_payload": TEST_URL,
        "input_type": "url",
        "include_full_outputs": False
    }
    
    try:
        response = requests.post(
            f"{BACKEND_URL}/api/truth/check/stream",
            json=payload,
            headers={"Content-Type": "application/json"},
            stream=True,  # 스트리밍 모드
            timeout=300  # 5분 타임아웃
        )
        
        if response.status_code != 200:
            print(f"❌ 오류: HTTP {response.status_code}")
            print(response.text)
            return False
        
        print("✅ 스트리밍 연결 성공!")
        print()
        print("─" * 60)
        print("실시간 Stage 진행 상황:")
        print("─" * 60)
        
        stage_count = 0
        
        # NDJSON 스트림 파싱
        for line in response.iter_lines():
            if not line:
                continue
            
            try:
                event = json.loads(line.decode('utf-8'))
                event_type = event.get('event')
                
                if event_type == 'stage_complete':
                    stage_count += 1
                    stage_name = event.get('stage', 'unknown')
                    print(f"  [{stage_count}] ✓ {stage_name} 완료")
                    
                elif event_type == 'complete':
                    print()
                    print("─" * 60)
                    print("🎉 전체 파이프라인 완료!")
                    print("─" * 60)
                    
                    data = event.get('data', {})
                    print(f"판정 결과: {data.get('label', 'N/A')}")
                    print(f"신뢰도: {data.get('confidence', 0):.2%}")
                    print(f"요약: {data.get('summary', 'N/A')}")
                    print(f"근거 개수: {len(data.get('citations', []))}개")
                    return True
                    
                elif event_type == 'error':
                    error_data = event.get('data', {})
                    print(f"\n❌ 에러 발생: {error_data.get('message', 'Unknown')}")
                    return False
                    
            except json.JSONDecodeError as e:
                print(f"⚠️  JSON 파싱 실패: {line[:100]}")
                continue
        
        print("\n⚠️  스트림이 예상치 못하게 종료되었습니다.")
        return False
        
    except requests.exceptions.Timeout:
        print("❌ 타임아웃: 5분 내에 완료되지 않았습니다.")
        return False
    except requests.exceptions.ConnectionError:
        print("❌ 연결 실패: Backend가 실행 중인지 확인하세요.")
        return False
    except Exception as e:
        print(f"❌ 예외 발생: {e}")
        import traceback
        traceback.print_exc()
        return False

def test_sync_verification():
    """동기식 엔드포인트 테스트 (기존 방식)"""
    print("\n" + "=" * 60)
    print("📨 동기식 검증 테스트 (비교용)")
    print("=" * 60)
    
    payload = {
        "input_payload": TEST_URL,
        "input_type": "url",
        "include_full_outputs": False
    }
    
    try:
        print("요청 전송 중... (완료까지 시간이 걸릴 수 있습니다)")
        response = requests.post(
            f"{BACKEND_URL}/truth/check",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=300
        )
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 동기식 검증 완료!")
            print(f"판정 결과: {result.get('label', 'N/A')}")
            print(f"신뢰도: {result.get('confidence', 0):.2%}")
            return True
        else:
            print(f"❌ 오류: HTTP {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ 예외 발생: {e}")
        return False

if __name__ == "__main__":
    print("\n🚀 OLaLA Frontend-Backend 연동 테스트 시작\n")
    
    # 스트리밍 테스트
    streaming_ok = test_streaming_verification()
    
    # 동기식 테스트 (선택사항)
    # sync_ok = test_sync_verification()
    
    print("\n" + "=" * 60)
    print("테스트 결과 요약")
    print("=" * 60)
    print(f"스트리밍 테스트: {'✅ 성공' if streaming_ok else '❌ 실패'}")
    # print(f"동기식 테스트: {'✅ 성공' if sync_ok else '❌ 실패'}")
    print()
    
    sys.exit(0 if streaming_ok else 1)
