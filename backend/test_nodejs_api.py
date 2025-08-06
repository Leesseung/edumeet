#!/usr/bin/env python3
"""
Node.js backend API 테스트 스크립트
"""

import requests
import json

def test_nodejs_health():
    """Node.js 서버 헬스체크"""
    try:
        response = requests.get("http://localhost:3001/")
        print(f"✅ Node.js 헬스체크: {response.status_code}")
        if response.status_code == 200:
            print(f"응답: {response.text}")
        return True
    except Exception as e:
        print(f"❌ Node.js 서버 연결 실패: {e}")
        return False

def test_nodejs_extract():
    """Node.js 키워드 추출 테스트"""
    print("\n🔍 Node.js 키워드 추출 테스트...")
    url = "http://localhost:3001/api/extract-key-sentences"
    data = {
        "text": "오늘은 변수와 함수에 대해 배워보겠습니다. 변수는 데이터를 저장하는 공간입니다.",
        "extractKeywords": True,
        "extractSentences": True
    }
    
    try:
        response = requests.post(url, json=data, timeout=30)
        print(f"상태 코드: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 키워드 추출 성공: {result}")
            return True
        else:
            print(f"❌ 키워드 추출 실패: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 키워드 추출 오류: {e}")
        return False

def test_nodejs_llm():
    """Node.js LLM 요약 테스트"""
    print("\n🔍 Node.js LLM 요약 테스트...")
    url = "http://localhost:3001/api/llm-summarize"
    data = {
        "text": "오늘은 변수와 함수에 대해 배워보겠습니다. 변수는 데이터를 저장하는 공간입니다."
    }
    
    try:
        response = requests.post(url, json=data, timeout=30)
        print(f"상태 코드: {response.status_code}")
        print(f"응답 헤더: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ LLM 요약 성공!")
            print(f"요약: {result.get('summary', 'No summary')[:200]}...")
            return True
        else:
            print(f"❌ LLM 요약 실패: {response.text}")
            try:
                error_json = response.json()
                print(f"에러 상세: {json.dumps(error_json, ensure_ascii=False, indent=2)}")
            except:
                pass
            return False
    except Exception as e:
        print(f"❌ LLM API 오류: {e}")
        return False

def main():
    print("🚀 Node.js Backend API 테스트 시작...")
    print("=" * 60)
    
    results = []
    results.append(("Node.js 헬스체크", test_nodejs_health()))
    results.append(("Node.js 키워드 추출", test_nodejs_extract()))
    results.append(("Node.js LLM 요약", test_nodejs_llm()))
    
    print("\n" + "=" * 60)
    print("📊 Node.js 테스트 결과 요약:")
    for name, success in results:
        status = "✅ 성공" if success else "❌ 실패"
        print(f"  {name}: {status}")

if __name__ == "__main__":
    main()
