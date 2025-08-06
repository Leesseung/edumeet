from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import re
import math
import os
from collections import Counter
import numpy as np
from sentence_transformers import SentenceTransformer
from sklearn.metrics.pairwise import cosine_similarity
import nltk
import httpx
from dotenv import load_dotenv
import logging

# KoNLPy 선택적 import (설치되지 않은 경우 대비)
try:
    from konlpy.tag import Okt
    KONLPY_AVAILABLE = True
except ImportError:
    logger = logging.getLogger(__name__)
    logger.warning("KoNLPy가 설치되지 않았습니다. 기본 텍스트 처리 기능만 사용됩니다.")
    KONLPY_AVAILABLE = False
    Okt = None

# 환경 변수 로드
load_dotenv(dotenv_path="config.env")

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(title="교육 텍스트 요약 API", version="1.0.0")

# 요청 로깅 미들웨어
@app.middleware("http")
async def log_requests(request, call_next):
    print(f"🌐 요청: {request.method} {request.url}")
    logger.info(f"요청: {request.method} {request.url}")
    
    try:
        response = await call_next(request)
        print(f"🌐 응답: {response.status_code}")
        logger.info(f"응답: {response.status_code}")
        return response
    except Exception as e:
        print(f"🌐 미들웨어 오류: {e}")
        logger.error(f"미들웨어 오류: {e}")
        raise

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 전역 모델 초기화
embedding_model = None
okt = None

@app.on_event("startup")
async def startup_event():
    """앱 시작 시 모델 로드"""
    global embedding_model, okt
    try:
        # NLTK 데이터 다운로드
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt')
        
        # KoNLPy Okt 초기화 (가능한 경우만)
        if KONLPY_AVAILABLE:
            okt = Okt()
            logger.info("KoNLPy Okt 로드 완료")
        else:
            logger.warning("KoNLPy를 사용할 수 없습니다. 기본 기능으로 대체됩니다.")
        
        # 임베딩 모델 로드 (빠르고 가벼운 모델)
        embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
        logger.info("Sentence Transformer 모델 로드 완료")
    except Exception as e:
        logger.error(f"모델 로드 실패: {e}")

# 요청/응답 모델 정의
class TextExtractionRequest(BaseModel):
    text: str
    extractKeywords: bool = True
    extractSentences: bool = True

class TextExtractionResponse(BaseModel):
    keywords: Optional[List[str]] = None
    keySentences: Optional[List[str]] = None

class LLMSummarizeRequest(BaseModel):
    text: str

class LLMSummarizeResponse(BaseModel):
    summary: str

class TextFilterRequest(BaseModel):
    text: str
    similarity_threshold: float = 0.3
    min_sentence_length: int = 20

class TextFilterResponse(BaseModel):
    filtered_text: str
    removed_sentences: int
    total_sentences: int
    similarity_scores: Optional[List[float]] = None
    okt_analysis: Optional[str] = None

# 교육 분야 중요 품사 태그 (명사, 동사, 형용사 중심)
IMPORTANT_POS_TAGS = {
    'Noun',      # 명사
    'Verb',      # 동사  
    'Adjective', # 형용사
    'VerbPrefix' # 동사 접두사
}

# 구어체 표현 패턴 (정규표현식으로 제거할 패턴들)
COLLOQUIAL_PATTERNS = [
    r'\b(음|어|아|오|와|헉|어머|아이고)\b',  # 감탄사
    r'\b(그냥|뭔가|막|좀|진짜|정말|완전|엄청|되게|너무)\s+',  # 구어체 부사
    r'(.{1,10}?)\1{2,}',  # 반복 표현
    r'\s+',  # 과도한 공백
]

# 교육 관련 중요 키워드 패턴 (가중치 부여용)
EDUCATION_KEYWORD_PATTERNS = [
    r'(개념|정의|원리|법칙|이론|공식|정리|증명)',
    r'(예시|사례|문제|해결|방법|과정|단계|절차)',
    r'(결과|결론|요약|정리|중요|핵심|주요)',
    r'(기본|기초|응용|활용|실습|연습|복습)',
    r'(시험|평가|과제|숙제|학습|이해|암기|기억|분석|비교)'
]

def preprocess_education_text(text: str) -> str:
    """교육 특화 텍스트 전처리 (구어체 → 문어체) - 개선된 버전"""
    processed_text = text
    
    # 구어체 패턴들을 순차적으로 정리
    for pattern in COLLOQUIAL_PATTERNS:
        if pattern == r'\s+':  # 마지막에 공백 정리
            processed_text = re.sub(pattern, ' ', processed_text)
        else:
            processed_text = re.sub(pattern, '', processed_text)
    
    return processed_text.strip()

def analyze_morphology_with_okt(text: str) -> List[tuple]:
    """KoNLPy Okt를 사용한 한국어 형태소 분석"""
    if not KONLPY_AVAILABLE or not okt:
        logger.warning("OKT가 사용할 수 없습니다. 기본 단어 분석을 사용합니다.")
        # 간단한 기본 분석으로 대체
        words = re.findall(r'[가-힣]{2,}', text)
        return [(word, 'Noun') for word in words]
    
    try:
        # 텍스트 전처리
        preprocessed_text = preprocess_education_text(text)
        
        # 형태소 분석 및 품사 태깅
        morphs_with_pos = okt.pos(preprocessed_text, stem=True)
        
        # 중요한 품사만 필터링 (명사, 동사, 형용사 등)
        important_morphs = [
            (word, pos) for word, pos in morphs_with_pos
            if pos in IMPORTANT_POS_TAGS and len(word) > 1
        ]
        
        return important_morphs
        
    except Exception as e:
        logger.error(f"형태소 분석 오류: {e}")
        return []

def extract_keywords_with_okt(text: str, top_k: int = 15) -> List[str]:
    """OKT 기반 키워드 추출 (품사 태깅 활용)"""
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    
    # 전체 텍스트에서 형태소 분석
    all_morphs = analyze_morphology_with_okt(text)
    
    if not all_morphs:
        logger.warning("형태소 분석 결과가 없습니다.")
        return []
    
    # 단어별 빈도 계산 (품사별 가중치 적용)
    word_freq = Counter()
    for word, pos in all_morphs:
        # 품사별 가중치
        weight = 1.0
        if pos == 'Noun':
            weight = 1.5  # 명사 가중치
        elif pos == 'Verb':
            weight = 1.3  # 동사 가중치
        elif pos == 'Adjective':
            weight = 1.2  # 형용사 가중치
        
        # 교육 키워드 추가 가중치
        for pattern in EDUCATION_KEYWORD_PATTERNS:
            if re.search(pattern, word):
                weight *= 1.5
                break
        
        word_freq[word] += weight
    
    # 문서 빈도 계산 (DF)
    doc_freq = Counter()
    for sentence in sentences:
        sentence_morphs = analyze_morphology_with_okt(sentence)
        sentence_words = set([word for word, _ in sentence_morphs])
        for word in sentence_words:
            doc_freq[word] += 1
    
    # TF-IDF 계산
    tfidf = {}
    total_docs = len(sentences)
    total_words = sum(word_freq.values())
    
    for word, freq in word_freq.items():
        tf = freq / total_words
        idf = math.log(total_docs / (doc_freq[word] if doc_freq[word] > 0 else 1))
        tfidf[word] = tf * idf
    
    # 상위 키워드 반환
    sorted_keywords = sorted(tfidf.items(), key=lambda x: x[1], reverse=True)
    return [word for word, _ in sorted_keywords[:top_k]]

# 기존 함수들도 유지 (호환성)
def analyze_morphology(text: str) -> List[str]:
    """기존 형태소 분석 (호환성 유지)"""
    morphs_with_pos = analyze_morphology_with_okt(text)
    return [word for word, _ in morphs_with_pos]

def extract_keywords(text: str, top_k: int = 15) -> List[str]:
    """교육 특화 TF-IDF 키워드 추출"""
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if s.strip()]
    all_words = analyze_morphology(text)
    
    # 단어 빈도 계산 (TF) - 교육 키워드 가중치 적용
    word_freq = Counter()
    for word in all_words:
        weight = 1.5 if word in EDUCATION_KEYWORDS else 1.0
        word_freq[word] += weight
    
    # 문서 빈도 계산 (DF)
    doc_freq = Counter()
    for sentence in sentences:
        sentence_words = set(analyze_morphology(sentence))
        for word in sentence_words:
            doc_freq[word] += 1
    
    # TF-IDF 계산
    tfidf = {}
    total_docs = len(sentences)
    total_words = len(all_words)
    
    for word, freq in word_freq.items():
        tf = freq / total_words
        idf = math.log(total_docs / (doc_freq[word] if doc_freq[word] > 0 else 1))
        tfidf[word] = tf * idf
    
    # 상위 키워드 반환
    sorted_keywords = sorted(tfidf.items(), key=lambda x: x[1], reverse=True)
    return [word for word, _ in sorted_keywords[:top_k]]

def extract_key_sentences(text: str, top_k: int = 6) -> List[str]:
    """교육 특화 핵심 문장 추출 (OKT 기반)"""
    sentences = [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 15]
    keywords = extract_keywords_with_okt(text, 25)
    keyword_set = set(keywords)
    
    # 교육 특화 문장 점수 계산
    sentence_scores = []
    for index, sentence in enumerate(sentences):
        words = analyze_morphology(sentence)
        keyword_count = sum(1 for word in words if word in keyword_set)
        
        # 기본 키워드 점수
        score = keyword_count / max(len(words), 1)
        
        # 교육 특화 가중치
        if re.search(r'중요|핵심|기본|개념|정의|원리', sentence):
            score *= 1.3
        if re.search(r'예를 들어|예시|사례|실습', sentence):
            score *= 1.2
        if re.search(r'정리하면|요약하면|결론|마무리', sentence):
            score *= 1.4
        if re.search(r'시험|평가|과제', sentence):
            score *= 1.2
        
        # 위치 가중치 (도입부와 마무리 부분 중요)
        position = index / len(sentences)
        if position < 0.2 or position > 0.8:
            score *= 1.1
        
        sentence_scores.append({
            'sentence': sentence,
            'score': score,
            'length': len(sentence),
            'position': index
        })
    
    # 점수순으로 정렬하되, 적절한 길이의 문장만 선별
    filtered_scores = [
        item for item in sentence_scores 
        if 25 < item['length'] < 200
    ]
    
    # 점수순 정렬 후 상위 선택, 원래 순서로 재정렬
    top_sentences = sorted(filtered_scores, key=lambda x: x['score'], reverse=True)[:top_k]
    top_sentences.sort(key=lambda x: x['position'])
    
    return [item['sentence'] for item in top_sentences]

def tokenize_sentences(text: str) -> List[str]:
    """문장 분할"""
    try:
        sentences = nltk.sent_tokenize(text)
        return [s.strip() for s in sentences if len(s.strip()) > 10]
    except Exception as e:
        logger.warning(f"NLTK 토큰화 실패, 간단한 분할 사용: {e}")
        return [s.strip() for s in re.split(r'[.!?]+', text) if len(s.strip()) > 10]

def filter_text_by_similarity_with_okt(text: str, similarity_threshold: float = 0.3, min_sentence_length: int = 20) -> Dict[str, Any]:
    """OKT 기반 개선된 유사도 필터링"""
    if not embedding_model or not okt:
        raise HTTPException(status_code=500, detail="모델이 로드되지 않았습니다.")
    
    # 문장 분할
    sentences = tokenize_sentences(text)
    sentences = [s for s in sentences if len(s) >= min_sentence_length]
    
    if len(sentences) < 2:
        return {
            "filtered_text": text,
            "removed_sentences": 0,
            "total_sentences": len(sentences),
            "okt_analysis": "문장 수가 부족하여 필터링하지 않음"
        }
    
    try:
        # 각 문장에서 중요한 형태소만 추출하여 임베딩에 사용
        processed_sentences = []
        morphology_info = []
        
        for sentence in sentences:
            # OKT로 형태소 분석
            morphs = analyze_morphology_with_okt(sentence)
            important_words = [word for word, pos in morphs if len(word) > 1]
            
            # 중요한 단어들로 문장 재구성
            processed_sentence = ' '.join(important_words) if important_words else sentence
            processed_sentences.append(processed_sentence)
            morphology_info.append({
                "original": sentence,
                "morphs": morphs,
                "important_words": important_words
            })
        
        # 처리된 문장들로 임베딩 생성
        embeddings = embedding_model.encode(processed_sentences)
        
        # 전체 중요 키워드 기반 기준 임베딩 생성
        all_important_words = []
        for info in morphology_info:
            all_important_words.extend(info["important_words"])
        
        if all_important_words:
            # 핵심 키워드들의 임베딩을 기준점으로 사용
            core_keywords = extract_keywords_with_okt(text, 10)
            reference_text = ' '.join(core_keywords)
            reference_embedding = embedding_model.encode([reference_text])
        else:
            # 평균 임베딩을 기준점으로 사용
            reference_embedding = np.mean(embeddings, axis=0).reshape(1, -1)
        
        # 각 문장과 기준점 간의 유사도 계산
        similarities = cosine_similarity(embeddings, reference_embedding).flatten()
        
        # 임계값 이상의 문장만 선택
        filtered_indices = [
            i for i, sim in enumerate(similarities) 
            if sim >= similarity_threshold
        ]
        
        # 최소 문장 수 보장 (너무 많이 필터링되는 것 방지)
        min_keep = max(2, int(len(sentences) * 0.4))  # 40% 이상은 보장
        if len(filtered_indices) < min_keep:
            # 유사도 순으로 정렬해서 상위 문장들 보장
            indices_with_sim = [(i, sim) for i, sim in enumerate(similarities)]
            indices_with_sim.sort(key=lambda x: x[1], reverse=True)
            filtered_indices = [i for i, _ in indices_with_sim[:min_keep]]
        
        # 원래 순서대로 정렬
        filtered_indices.sort()
        filtered_sentences = [sentences[i] for i in filtered_indices]
        
        return {
            "filtered_text": " ".join(filtered_sentences),
            "removed_sentences": len(sentences) - len(filtered_sentences),
            "total_sentences": len(sentences),
            "similarity_scores": [float(sim) for sim in similarities],
            "okt_analysis": f"형태소 분석 완료, 핵심 키워드: {core_keywords[:5] if 'core_keywords' in locals() else '없음'}"
        }
        
    except Exception as e:
        logger.error(f"OKT 기반 유사도 필터링 오류: {e}")
        # 오류 시 기존 방식으로 폴백
        return filter_text_by_similarity(text, similarity_threshold, min_sentence_length)

def filter_text_by_similarity(text: str, similarity_threshold: float = 0.3, min_sentence_length: int = 20) -> Dict[str, Any]:
    """유사도 기반 텍스트 필터링"""
    if not embedding_model:
        raise HTTPException(status_code=500, detail="임베딩 모델이 로드되지 않았습니다.")
    
    # 문장 분할
    sentences = tokenize_sentences(text)
    sentences = [s for s in sentences if len(s) >= min_sentence_length]
    
    if len(sentences) < 2:
        return {
            "filtered_text": text,
            "removed_sentences": 0,
            "total_sentences": len(sentences)
        }
    
    try:
        # 문장 임베딩 생성
        embeddings = embedding_model.encode(sentences)
        
        # 전체 텍스트의 평균 임베딩 계산 (기준점)
        mean_embedding = np.mean(embeddings, axis=0).reshape(1, -1)
        
        # 각 문장과 평균 임베딩 간의 유사도 계산
        similarities = cosine_similarity(embeddings, mean_embedding).flatten()
        
        # 임계값 이상의 문장만 선택
        filtered_sentences = [
            sentences[i] for i, sim in enumerate(similarities) 
            if sim >= similarity_threshold
        ]
        
        # 최소 문장 수 보장 (너무 많이 필터링되는 것 방지)
        if len(filtered_sentences) < max(2, len(sentences) * 0.3):
            # 유사도 순으로 정렬해서 상위 30% 이상은 보장
            min_keep = max(2, int(len(sentences) * 0.3))
            indices_with_sim = [(i, sim) for i, sim in enumerate(similarities)]
            indices_with_sim.sort(key=lambda x: x[1], reverse=True)
            filtered_sentences = [sentences[i] for i, _ in indices_with_sim[:min_keep]]
        
        return {
            "filtered_text": " ".join(filtered_sentences),
            "removed_sentences": len(sentences) - len(filtered_sentences),
            "total_sentences": len(sentences)
        }
        
    except Exception as e:
        logger.error(f"유사도 필터링 오류: {e}")
        # 오류 시 원본 텍스트 반환
        return {
            "filtered_text": text,
            "removed_sentences": 0,
            "total_sentences": len(sentences)
        }

@app.post("/api/extract-key-sentences", response_model=TextExtractionResponse)
async def extract_key_sentences_api(request: TextExtractionRequest):
    """키워드/문장 추출 API"""
    try:
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="텍스트를 입력해주세요.")
        
        result = {}
        
        if request.extractKeywords:
            result["keywords"] = extract_keywords_with_okt(request.text, 10)
        
        if request.extractSentences:
            result["keySentences"] = extract_key_sentences(request.text, 3)
        
        return TextExtractionResponse(**result)
        
    except Exception as e:
        logger.error(f"키워드/문장 추출 오류: {e}")
        raise HTTPException(status_code=500, detail="키워드/문장 추출 중 오류가 발생했습니다.")

@app.post("/api/llm-summarize", response_model=LLMSummarizeResponse)
async def llm_summarize_api(request: LLMSummarizeRequest):
    """LLM 요약 API"""
    print("🔥 LLM API 호출됨!")  # 강제 출력
    logger.info("🔥 LLM API 요청 받음")
    try:
        print(f"🔥 요청 텍스트 길이: {len(request.text) if request.text else 0}")
        logger.info(f"LLM API 요청 받음: {len(request.text) if request.text else 0}자")
        
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="요약할 텍스트를 입력해주세요.")
        
        openai_api_key = os.getenv("OPENAI_API_KEY")
        logger.info(f"API 키 확인: {bool(openai_api_key)}, 길이: {len(openai_api_key) if openai_api_key else 0}")
        
        # API 키가 없으면 더미 응답
        if not openai_api_key or openai_api_key == "your_openai_api_key_here":
            summary = f"""📝 **요약 결과**

핵심 내용: {request.text[:80]}...

이 문서는 중요한 정보를 포함하고 있으며, 주요 논점들이 체계적으로 제시되어 있습니다. 전반적으로 유용한 참고 자료로 활용할 수 있을 것으로 판단됩니다.

⚠️ *실제 AI 요약을 사용하려면 .env 파일에 OPENAI_API_KEY를 설정하세요*"""
            
            return LLMSummarizeResponse(summary=summary)

        # SSAFY GMS API 또는 OpenAI API 호출
        is_gms_api_key = openai_api_key.startswith('S13P')  # SSAFY GMS API 키 패턴 수정
        api_url = ("https://gms.ssafy.io/gmsapi/api.openai.com/v1/chat/completions" 
                  if is_gms_api_key else "https://api.openai.com/v1/chat/completions")

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                api_url,
                headers={
                    "Authorization": f"Bearer {openai_api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": """당신은 교육 전문 요약 AI입니다. 선생님의 1시간 강의 내용을 학생들이 이해하기 쉽게 요약해주세요.

요약 형식:
📚 **주요 학습 내용**
- 핵심 개념과 정의
- 중요한 원리나 법칙

🎯 **핵심 포인트**  
- 꼭 기억해야 할 내용
- 시험에 나올 만한 중요 사항

💡 **실습/예시**
- 구체적인 사례나 예시
- 실제 적용 방법

📝 **정리**
- 전체 내용을 한 문장으로 요약
- 다음 학습과의 연결점"""
                        },
                        {
                            "role": "user",
                            "content": f"다음은 선생님이 1시간 동안 진행한 수업 내용입니다. 학생들의 학습을 위해 체계적으로 요약해주세요:\n\n{request.text}"
                        }
                    ],
                    "temperature": 0.3,
                    "max_tokens": 500
                }
            )
        
        if response.status_code != 200:
            error_text = response.text
            logger.error(f"LLM API 오류: {response.status_code} {error_text}")
            logger.error(f"사용된 API URL: {api_url}")
            logger.error(f"API 키 패턴: {openai_api_key[:10]}...")
            raise HTTPException(status_code=500, detail=f"LLM API 호출 실패 (HTTP {response.status_code}): {error_text[:100]}")
        
        data = response.json()
        summary = data.get("choices", [{}])[0].get("message", {}).get("content")
        
        if not summary:
            raise HTTPException(status_code=500, detail="요약 생성에 실패했습니다.")
        
        return LLMSummarizeResponse(summary=summary.strip())
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        logger.error(f"LLM 요약 오류: {e}")
        logger.error(f"상세 오류: {traceback.format_exc()}")
        logger.error(f"API 키 존재: {bool(openai_api_key)}")
        logger.error(f"API 키 패턴: {openai_api_key[:10] if openai_api_key else 'None'}...")
        raise HTTPException(status_code=500, detail=f"LLM 요약 중 오류: {str(e)}")

@app.post("/api/filter-text", response_model=TextFilterResponse)
async def filter_text_api(request: TextFilterRequest):
    """유사도 기반 텍스트 필터링 API"""
    try:
        if not request.text or not request.text.strip():
            raise HTTPException(status_code=400, detail="필터링할 텍스트를 입력해주세요.")
        
        result = filter_text_by_similarity_with_okt(
            request.text, 
            request.similarity_threshold, 
            request.min_sentence_length
        )
        
        return TextFilterResponse(**result)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"텍스트 필터링 오류: {e}")
        raise HTTPException(status_code=500, detail="텍스트 필터링 중 오류가 발생했습니다.")

@app.get("/")
async def root():
    """헬스 체크"""
    return {"message": "🚀 교육 텍스트 요약 API 서버 실행 중", "status": "ok"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port) 