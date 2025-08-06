<template>
  <div class="document-summary-container">
    <!-- Header Section -->
    <div class="header-section">
      <h1 class="page-title">📚 AI 문서 요약 시스템</h1>
      <p class="page-subtitle">강의 내용을 입력하면 AI가 자동으로 요약해드립니다</p>
    </div>

    <!-- Input Section -->
    <div class="input-section">
      <div class="input-group">
        <label for="textInput" class="input-label">
          📝 강의 내용 입력
        </label>
        <textarea
          id="textInput"
          v-model="inputText"
          class="text-input"
          placeholder="여기에 강의 내용을 입력하세요. 예: 오늘은 변수와 함수에 대해 배워보겠습니다..."
          rows="8"
          :disabled="isLoading"
        ></textarea>
      </div>

      <!-- API Options -->
      <div class="options-section">
        <h3 class="options-title">처리 옵션</h3>
        <div class="option-buttons">
          <button
            @click="extractKeyInfo"
            :disabled="!inputText.trim() || isLoading"
            class="btn btn-secondary"
          >
            🔑 키워드 & 핵심문장 추출
          </button>
          <button
            @click="summarizeWithLLM"
            :disabled="!inputText.trim() || isLoading"
            class="btn btn-primary"
          >
            🤖 AI 요약
          </button>
          <button
            @click="filterText"
            :disabled="!inputText.trim() || isLoading"
            class="btn btn-outline"
          >
            🎯 텍스트 필터링
          </button>
        </div>
      </div>
    </div>

    <!-- Loading Section -->
    <div v-if="isLoading" class="loading-section">
      <div class="spinner"></div>
      <p>{{ loadingMessage }}</p>
    </div>

    <!-- Results Section -->
    <div v-if="results.length > 0" class="results-section">
      <h2 class="results-title">📋 처리 결과</h2>
      
      <div v-for="(result, index) in results" :key="index" class="result-card">
        <!-- Keywords & Key Sentences Result -->
        <div v-if="result.type === 'extract'" class="extract-result">
          <h3 class="result-subtitle">🔑 키워드 & 핵심문장 추출 결과</h3>
          
          <div v-if="result.data.keywords" class="keywords-section">
            <h4>📌 추출된 키워드</h4>
            <div class="keywords-container">
              <span 
                v-for="keyword in result.data.keywords" 
                :key="keyword"
                class="keyword-tag"
              >
                {{ keyword }}
              </span>
            </div>
          </div>

          <div v-if="result.data.keySentences" class="sentences-section">
            <h4>📝 핵심 문장</h4>
            <ul class="sentences-list">
              <li 
                v-for="sentence in result.data.keySentences" 
                :key="sentence"
                class="sentence-item"
              >
                {{ sentence }}
              </li>
            </ul>
          </div>
        </div>

        <!-- LLM Summary Result -->
        <div v-if="result.type === 'llm'" class="llm-result">
          <h3 class="result-subtitle">🤖 AI 요약 결과</h3>
          <div class="summary-content" v-html="formatSummary(result.data.summary)"></div>
        </div>

        <!-- Filter Result -->
        <div v-if="result.type === 'filter'" class="filter-result">
          <h3 class="result-subtitle">🎯 텍스트 필터링 결과</h3>
          
          <div class="filter-stats">
            <div class="stat-item">
              <span class="stat-label">총 문장:</span>
              <span class="stat-value">{{ result.data.total_sentences }}개</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">제거된 문장:</span>
              <span class="stat-value">{{ result.data.removed_sentences }}개</span>
            </div>
            <div v-if="result.data.okt_analysis" class="stat-item">
              <span class="stat-label">분석 정보:</span>
              <span class="stat-value">{{ result.data.okt_analysis }}</span>
            </div>
          </div>

          <div class="filtered-text">
            <h4>✨ 필터링된 텍스트</h4>
            <p class="filtered-content">{{ result.data.filtered_text }}</p>
          </div>
        </div>

        <div class="result-timestamp">
          {{ formatTimestamp(result.timestamp) }}
        </div>
      </div>
    </div>

    <!-- Error Section -->
    <div v-if="error" class="error-section">
      <div class="error-card">
        <h3>❌ 오류 발생</h3>
        <p>{{ error }}</p>
        <button @click="clearError" class="btn btn-outline">닫기</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive } from 'vue'

// Reactive data
const inputText = ref('')
const isLoading = ref(false)
const loadingMessage = ref('')
const results = ref([])
const error = ref('')

// API Base URL - FastAPI 서버 주소
const API_BASE_URL = 'http://localhost:8000'

// API 호출 함수들
const makeApiCall = async (endpoint, data) => {
  try {
    const response = await fetch(`${API_BASE_URL}${endpoint}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    })

    if (!response.ok) {
      const errorData = await response.text()
      throw new Error(`HTTP ${response.status}: ${errorData}`)
    }

    return await response.json()
  } catch (error) {
    if (error.name === 'TypeError' && error.message.includes('fetch')) {
      throw new Error('FastAPI 서버에 연결할 수 없습니다. 서버가 실행 중인지 확인해주세요.')
    }
    throw error
  }
}

// 키워드 & 핵심문장 추출
const extractKeyInfo = async () => {
  isLoading.value = true
  loadingMessage.value = '키워드와 핵심문장을 추출하고 있습니다...'
  error.value = ''

  try {
    const data = await makeApiCall('/api/extract-key-sentences', {
      text: inputText.value.trim(),
      extractKeywords: true,
      extractSentences: true
    })

    results.value.unshift({
      type: 'extract',
      data: data,
      timestamp: new Date()
    })
  } catch (err) {
    error.value = err.message
  } finally {
    isLoading.value = false
    loadingMessage.value = ''
  }
}

// LLM 요약
const summarizeWithLLM = async () => {
  isLoading.value = true
  loadingMessage.value = 'AI가 텍스트를 요약하고 있습니다...'
  error.value = ''

  try {
    const data = await makeApiCall('/api/llm-summarize', {
      text: inputText.value.trim()
    })

    results.value.unshift({
      type: 'llm',
      data: data,
      timestamp: new Date()
    })
  } catch (err) {
    error.value = err.message
  } finally {
    isLoading.value = false
    loadingMessage.value = ''
  }
}

// 텍스트 필터링
const filterText = async () => {
  isLoading.value = true
  loadingMessage.value = '텍스트를 필터링하고 있습니다...'
  error.value = ''

  try {
    const data = await makeApiCall('/api/filter-text', {
      text: inputText.value.trim(),
      similarity_threshold: 0.3,
      min_sentence_length: 20
    })

    results.value.unshift({
      type: 'filter',
      data: data,
      timestamp: new Date()
    })
  } catch (err) {
    error.value = err.message
  } finally {
    isLoading.value = false
    loadingMessage.value = ''
  }
}

// 유틸리티 함수들
const formatSummary = (summary) => {
  return summary
    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
    .replace(/📚|🎯|💡|📝/g, '<span class="emoji">$&</span>')
    .replace(/\n/g, '<br>')
}

const formatTimestamp = (timestamp) => {
  return timestamp.toLocaleString('ko-KR', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}

const clearError = () => {
  error.value = ''
}
</script>

<style scoped>
.document-summary-container {
  max-width: 1200px;
  margin: 0 auto;
  padding: 2rem;
  font-family: 'Noto Sans KR', sans-serif;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  min-height: 100vh;
}

/* Header Section */
.header-section {
  text-align: center;
  margin-bottom: 3rem;
  color: white;
}

.page-title {
  font-size: 2.5rem;
  font-weight: 700;
  margin-bottom: 0.5rem;
  text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
}

.page-subtitle {
  font-size: 1.2rem;
  opacity: 0.9;
  margin-bottom: 0;
}

/* Input Section */
.input-section {
  background: white;
  border-radius: 16px;
  padding: 2rem;
  margin-bottom: 2rem;
  box-shadow: 0 10px 30px rgba(0,0,0,0.1);
}

.input-group {
  margin-bottom: 2rem;
}

.input-label {
  display: block;
  font-size: 1.1rem;
  font-weight: 600;
  color: #333;
  margin-bottom: 0.8rem;
}

.text-input {
  width: 100%;
  padding: 1rem;
  border: 2px solid #e1e5e9;
  border-radius: 12px;
  font-size: 1rem;
  line-height: 1.6;
  resize: vertical;
  transition: border-color 0.3s ease;
  font-family: inherit;
}

.text-input:focus {
  outline: none;
  border-color: #667eea;
  box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
}

.text-input:disabled {
  background-color: #f8f9fa;
  cursor: not-allowed;
}

/* Options Section */
.options-section {
  border-top: 1px solid #e1e5e9;
  padding-top: 2rem;
}

.options-title {
  font-size: 1.3rem;
  font-weight: 600;
  color: #333;
  margin-bottom: 1rem;
}

.option-buttons {
  display: flex;
  gap: 1rem;
  flex-wrap: wrap;
}

/* Buttons */
.btn {
  padding: 0.8rem 1.5rem;
  border: none;
  border-radius: 8px;
  font-size: 1rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  display: inline-flex;
  align-items: center;
  gap: 0.5rem;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(102, 126, 234, 0.3);
}

.btn-secondary {
  background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
  color: white;
}

.btn-secondary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 8px 20px rgba(116, 185, 255, 0.3);
}

.btn-outline {
  background: transparent;
  color: #667eea;
  border: 2px solid #667eea;
}

.btn-outline:hover:not(:disabled) {
  background: #667eea;
  color: white;
}

/* Loading Section */
.loading-section {
  text-align: center;
  padding: 3rem;
  color: white;
}

.spinner {
  width: 50px;
  height: 50px;
  border: 4px solid rgba(255,255,255,0.3);
  border-top: 4px solid white;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin: 0 auto 1rem;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}

/* Results Section */
.results-section {
  margin-top: 2rem;
}

.results-title {
  color: white;
  font-size: 1.8rem;
  font-weight: 700;
  margin-bottom: 1.5rem;
  text-align: center;
}

.result-card {
  background: white;
  border-radius: 16px;
  padding: 2rem;
  margin-bottom: 2rem;
  box-shadow: 0 10px 30px rgba(0,0,0,0.1);
  position: relative;
}

.result-subtitle {
  font-size: 1.4rem;
  font-weight: 600;
  color: #333;
  margin-bottom: 1.5rem;
  padding-bottom: 0.5rem;
  border-bottom: 2px solid #f1f3f4;
}

/* Keywords Section */
.keywords-section {
  margin-bottom: 2rem;
}

.keywords-section h4 {
  font-size: 1.1rem;
  font-weight: 600;
  color: #555;
  margin-bottom: 1rem;
}

.keywords-container {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.keyword-tag {
  background: linear-gradient(135deg, #74b9ff 0%, #0984e3 100%);
  color: white;
  padding: 0.5rem 1rem;
  border-radius: 20px;
  font-size: 0.9rem;
  font-weight: 500;
}

/* Sentences Section */
.sentences-section h4 {
  font-size: 1.1rem;
  font-weight: 600;
  color: #555;
  margin-bottom: 1rem;
}

.sentences-list {
  list-style: none;
  padding: 0;
}

.sentence-item {
  background: #f8f9fa;
  padding: 1rem;
  margin-bottom: 0.8rem;
  border-radius: 8px;
  border-left: 4px solid #667eea;
  line-height: 1.6;
}

/* LLM Result */
.summary-content {
  background: #f8f9fa;
  padding: 1.5rem;
  border-radius: 12px;
  line-height: 1.8;
  font-size: 1rem;
}

.summary-content .emoji {
  font-size: 1.2em;
  margin-right: 0.5rem;
}

/* Filter Result */
.filter-stats {
  display: flex;
  gap: 2rem;
  margin-bottom: 1.5rem;
  flex-wrap: wrap;
}

.stat-item {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.stat-label {
  font-size: 0.9rem;
  color: #666;
  font-weight: 500;
}

.stat-value {
  font-size: 1.1rem;
  font-weight: 600;
  color: #333;
}

.filtered-text h4 {
  font-size: 1.1rem;
  font-weight: 600;
  color: #555;
  margin-bottom: 1rem;
}

.filtered-content {
  background: #f8f9fa;
  padding: 1.5rem;
  border-radius: 12px;
  line-height: 1.7;
  margin: 0;
}

/* Timestamp */
.result-timestamp {
  position: absolute;
  top: 1rem;
  right: 1.5rem;
  font-size: 0.85rem;
  color: #666;
}

/* Error Section */
.error-section {
  margin-top: 2rem;
}

.error-card {
  background: #fff;
  border: 2px solid #ff6b6b;
  border-radius: 12px;
  padding: 1.5rem;
  text-align: center;
}

.error-card h3 {
  color: #ff6b6b;
  margin-bottom: 1rem;
}

.error-card p {
  color: #666;
  margin-bottom: 1rem;
}

/* Responsive Design */
@media (max-width: 768px) {
  .document-summary-container {
    padding: 1rem;
  }

  .page-title {
    font-size: 2rem;
  }

  .option-buttons {
    flex-direction: column;
  }

  .btn {
    width: 100%;
    justify-content: center;
  }

  .filter-stats {
    flex-direction: column;
    gap: 1rem;
  }

  .result-timestamp {
    position: static;
    text-align: center;
    margin-top: 1rem;
    padding-top: 1rem;
    border-top: 1px solid #e1e5e9;
  }
}
</style>

