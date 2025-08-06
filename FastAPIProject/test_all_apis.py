#!/usr/bin/env python3
"""
모든 API 엔드포인트 테스트 스크립트
"""

import requests
import json

def test_health_check():
    """헬스체크 테스트"""
    print("🔍 헬스체크 테스트...")
    try:
        response = requests.get("http://localhost:8000/")
        print(f"✅ 헬스체크: {response.status_code} - {response.json()}")
        return True
    except Exception as e:
        print(f"❌ 헬스체크 실패: {e}")
        return False

def test_extract_api():
    """키워드 추출 API 테스트"""
    print("\n🔍 키워드 추출 API 테스트...")
    url = "http://localhost:8000/api/extract-key-sentences"
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

def test_filter_api():
    """텍스트 필터링 API 테스트"""
    print("\n🔍 텍스트 필터링 API 테스트...")
    url = "http://localhost:8000/api/filter-text"
    data = {
        "text": "오늘은 변수와 함수에 대해 배워보겠습니다. 변수는 데이터를 저장하는 공간입니다. 함수는 특정 작업을 수행합니다.",
        "similarity_threshold": 0.3,
        "min_sentence_length": 20
    }
    
    try:
        response = requests.post(url, json=data, timeout=30)
        print(f"상태 코드: {response.status_code}")
        if response.status_code == 200:
            result = response.json()
            print(f"✅ 텍스트 필터링 성공")
            return True
        else:
            print(f"❌ 텍스트 필터링 실패: {response.text}")
            return False
    except Exception as e:
        print(f"❌ 텍스트 필터링 오류: {e}")
        return False

def test_llm_api():
    """LLM API 테스트"""
    print("\n🔍 LLM API 테스트...")
    url = "http://localhost:8000/api/llm-summarize"
    data = {
        "text": "오늘은 변수와 함수에 대해 배워보겠습니다. 변수는 데이터를 저장하는 공간입니다."
    }
    
    try:
        response = requests.post(url, json=data, timeout=30)
        print(f"상태 코드: {response.status_code}")
        print(f"응답 헤더: {dict(response.headers)}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ LLM 요약 성공: {result.get('summary', 'No summary')[:100]}...")
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
    print("🚀 전체 API 테스트 시작...")
    print("=" * 60)
    
    results = []
    results.append(("헬스체크", test_health_check()))
    results.append(("키워드 추출", test_extract_api()))
    results.append(("텍스트 필터링", test_filter_api()))
    results.append(("LLM 요약", test_llm_api()))
    
    print("\n" + "=" * 60)
    print("📊 테스트 결과 요약:")
    for name, success in results:
        status = "✅ 성공" if success else "❌ 실패"
        print(f"  {name}: {status}")
    
    failed_count = sum(1 for _, success in results if not success)
    if failed_count == 0:
        print("\n🎉 모든 테스트 통과!")
    else:
        print(f"\n⚠️ {failed_count}개 테스트 실패")

if __name__ == "__main__":
    main()
