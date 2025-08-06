#!/usr/bin/env python3
"""
LLM API 테스트 스크립트
FastAPI 서버의 LLM 요약 기능을 직접 테스트합니다.
"""

import requests
import json

def test_llm_api():
    """LLM API 테스트"""
    url = "http://localhost:8000/api/llm-summarize"
    
    # 테스트 데이터
    test_data = {
        "text": "오늘은 변수와 함수에 대해 배워보겠습니다. 변수는 데이터를 저장하는 공간이고, 함수는 특정 작업을 수행하는 코드 블록입니다. Python에서 변수를 선언할 때는 데이터 타입을 명시할 필요가 없습니다."
    }
    
    headers = {
        "Content-Type": "application/json"
    }
    
    print("🚀 LLM API 테스트 시작...")
    print(f"URL: {url}")
    print(f"Data: {json.dumps(test_data, ensure_ascii=False, indent=2)}")
    print("-" * 50)
    
    try:
        response = requests.post(url, json=test_data, headers=headers, timeout=30)
        
        print(f"상태 코드: {response.status_code}")
        print(f"응답 헤더: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print("✅ 성공!")
            print(f"요약 결과: {result.get('summary', 'No summary')}")
        else:
            print("❌ 에러 발생!")
            print(f"에러 내용: {response.text}")
            try:
                error_json = response.json()
                print(f"에러 상세: {json.dumps(error_json, ensure_ascii=False, indent=2)}")
            except:
                pass
                
    except requests.exceptions.RequestException as e:
        print(f"❌ 요청 실패: {e}")
    except Exception as e:
        print(f"❌ 예상치 못한 오류: {e}")

if __name__ == "__main__":
    test_llm_api()
