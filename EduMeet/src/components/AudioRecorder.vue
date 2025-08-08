<template>
  <div 
    v-if="isOpen" 
    class="audio-recorder-modal"
    :style="{ left: position.x + 'px', top: position.y + 'px' }"
    @mousedown="startDrag"
    @touchstart="startDrag"
  >
    <div class="modal-content">
      <div class="recorder-controls">
        <button 
          @click="toggleRecording" 
          :class="['record-btn', isRecording ? 'stop-btn' : 'start-btn']"
        >
          {{ isRecording ? '⏹️ 수업 종료' : '🎤 수업 시작' }}
        </button>
      </div>
      
      <div v-if="isRecording" class="recording-status">
        <div class="status-indicator">
          <span class="recording-dot"></span>
          녹음 중...
        </div>
        <div class="recording-time">
          {{ formatTime(recordingTime) }}
        </div>
        <div class="chunk-info">
          청크 {{ currentChunk }} / {{ totalChunks }}
        </div>
      </div>
      
      <div v-if="uploadStatus" class="upload-status">
        <div class="status-message" :class="uploadStatus.type">
          {{ uploadStatus.message }}
        </div>
        <div v-if="uploadStatus.progress" class="progress-bar">
          <div class="progress-fill" :style="{ width: uploadStatus.progress + '%' }"></div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onUnmounted, onMounted } from 'vue'

const props = defineProps({
  classId: {
    type: [String, Number],
    required: true
  },
  className: {
    type: String,
    default: ''
  },
  creatorName: {
    type: String,
    default: ''
  },
  isOpen: {
    type: Boolean,
    default: true
  }
})

const emit = defineEmits(['recording-started', 'recording-stopped', 'chunk-uploaded', 'close'])

// 모달 상태
const position = ref({ x: 50, y: 50 })
const isDragging = ref(false)
const dragOffset = ref({ x: 0, y: 0 })

// 녹음 상태
const isRecording = ref(false)
const mediaRecorder = ref(null)
const audioChunks = ref([])
const recordingTime = ref(0)
const recordingTimer = ref(null)
const chunkTimer = ref(null)

// 청크 관련
const CHUNK_DURATION = 5 * 60 * 1000 // 5분 (밀리초)
const currentChunk = ref(0)
const totalChunks = ref(0)
const chunkStartTime = ref(0)

// 업로드 상태
const uploadStatus = ref(null)

// API 기본 URL
const API_BASE_URL = 'http://localhost:3001'

// 드래그 시작
const startDrag = (event) => {
  event.preventDefault()
  isDragging.value = true
  
  const rect = event.currentTarget.getBoundingClientRect()
  dragOffset.value = {
    x: event.clientX - rect.left,
    y: event.clientY - rect.top
  }
  
  document.addEventListener('mousemove', onDrag)
  document.addEventListener('mouseup', stopDrag)
  document.addEventListener('touchmove', onDrag)
  document.addEventListener('touchend', stopDrag)
}

// 드래그 중
const onDrag = (event) => {
  if (!isDragging.value) return
  
  event.preventDefault()
  
  const clientX = event.clientX || event.touches[0].clientX
  const clientY = event.clientY || event.touches[0].clientY
  
  position.value = {
    x: clientX - dragOffset.value.x,
    y: clientY - dragOffset.value.y
  }
}

// 드래그 종료
const stopDrag = () => {
  isDragging.value = false
  document.removeEventListener('mousemove', onDrag)
  document.removeEventListener('mouseup', stopDrag)
  document.removeEventListener('touchmove', onDrag)
  document.removeEventListener('touchend', stopDrag)
}

// 녹음 토글 (시작/종료)
const toggleRecording = async () => {
  if (isRecording.value) {
    await stopRecording()
  } else {
    await startRecording()
  }
}

// 녹음 시작
const startRecording = async () => {
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ 
      audio: {
        sampleRate: 44100,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true
      } 
    })
    
    // WAV 포맷을 위한 설정 (백엔드에서 WAV 파일을 기대하므로)
    const options = {
      mimeType: 'audio/wav'
    }
    
    // WAV가 지원되지 않는 경우 대체 포맷 사용
    if (!MediaRecorder.isTypeSupported(options.mimeType)) {
      options.mimeType = 'audio/webm;codecs=opus'
      console.warn('WAV가 지원되지 않아 WebM/Opus 사용')
    }
    
    mediaRecorder.value = new MediaRecorder(stream, options)
    
    // 녹음 데이터 수집
    mediaRecorder.value.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.value.push(event.data)
      }
    }
    
    // 청크 전송
    mediaRecorder.value.onstop = () => {
      sendChunk()
    }
    
    // 녹음 시작
    mediaRecorder.value.start(1000) // 1초마다 데이터 수집
    isRecording.value = true
    recordingTime.value = 0
    currentChunk.value = 1
    chunkStartTime.value = Date.now()
    
    // 타이머 시작
    startTimers()
    
    // 백엔드에 수업 시작 알림
    await notifyRecordingStart()
    
    emit('recording-started')
    
  } catch (error) {
    console.error('녹음 시작 실패:', error)
    alert('마이크 권한이 필요합니다.')
  }
}

// 녹음 종료
const stopRecording = async () => {
  if (mediaRecorder.value && isRecording.value) {
    mediaRecorder.value.stop()
    mediaRecorder.value.stream.getTracks().forEach(track => track.stop())
    
    isRecording.value = false
    stopTimers()
    
    // 마지막 청크 전송
    if (audioChunks.value.length > 0) {
      await sendChunk()
    }
    
    // 백엔드에 수업 종료 알림
    await notifyRecordingStop()
    
    emit('recording-stopped')
  }
}

// 타이머 시작
const startTimers = () => {
  // 녹음 시간 타이머
  recordingTimer.value = setInterval(() => {
    recordingTime.value += 1000
  }, 1000)
  
  // 청크 타이머
  chunkTimer.value = setInterval(() => {
    if (isRecording.value) {
      // 현재 청크 종료 및 새 청크 시작
      if (mediaRecorder.value) {
        mediaRecorder.value.stop()
        mediaRecorder.value.start(1000)
      }
      currentChunk.value++
    }
  }, CHUNK_DURATION)
}

// 타이머 정지
const stopTimers = () => {
  if (recordingTimer.value) {
    clearInterval(recordingTimer.value)
    recordingTimer.value = null
  }
  if (chunkTimer.value) {
    clearInterval(chunkTimer.value)
    chunkTimer.value = null
  }
}

// 청크 전송 (HTTP API 사용)
const sendChunk = async () => {
  if (audioChunks.value.length === 0) return
  
  try {
    uploadStatus.value = {
      type: 'uploading',
      message: `청크 ${currentChunk.value} 전송 중...`,
      progress: 0
    }
    
    const audioBlob = new Blob(audioChunks.value, { 
      type: mediaRecorder.value.mimeType 
    })
    
    // FormData를 사용하여 파일 업로드
    const formData = new FormData()
    formData.append('audio', audioBlob, `chunk_${currentChunk.value}.wav`)
    
    // HTTP API를 통해 청크 업로드
    const response = await fetch(`${API_BASE_URL}/api/class/${props.classId}/update-recording`, {
      method: 'POST',
      body: formData
    })
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    
    const result = await response.json()
    console.log('✅ 청크 업로드 성공:', result)
    
    uploadStatus.value = {
      type: 'success',
      message: `청크 ${currentChunk.value} 업로드 완료`,
      progress: 100
    }
    
    emit('chunk-uploaded', {
      chunkNumber: currentChunk.value,
      filename: result.filename,
      timestamp: Date.now()
    })
    
    // 3초 후 상태 초기화
    setTimeout(() => {
      uploadStatus.value = null
    }, 3000)
    
  } catch (error) {
    console.error('청크 전송 실패:', error)
    uploadStatus.value = {
      type: 'error',
      message: `청크 ${currentChunk.value} 전송 실패: ${error.message}`,
      progress: 0
    }
  }
  
  // 청크 데이터 초기화
  audioChunks.value = []
}

// 수업 시작 알림
const notifyRecordingStart = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/class/${props.classId}/start-recording`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        className: props.className,
        creatorName: props.creatorName,
        startTime: Date.now()
      })
    })
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    
    const result = await response.json()
    console.log('✅ 수업 시작 알림 성공:', result)
    
  } catch (error) {
    console.error('수업 시작 알림 실패:', error)
  }
}

// 수업 종료 알림
const notifyRecordingStop = async () => {
  try {
    const response = await fetch(`${API_BASE_URL}/api/class/${props.classId}/stop-recording`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        endTime: Date.now(),
        totalChunks: currentChunk.value
      })
    })
    
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}: ${response.statusText}`)
    }
    
    const result = await response.json()
    console.log('✅ 수업 종료 알림 성공:', result)
    
  } catch (error) {
    console.error('수업 종료 알림 실패:', error)
  }
}

// 시간 포맷팅
const formatTime = (milliseconds) => {
  const seconds = Math.floor(milliseconds / 1000)
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes.toString().padStart(2, '0')}:${remainingSeconds.toString().padStart(2, '0')}`
}

// 컴포넌트 마운트 시 초기 위치 설정
onMounted(() => {
  // 화면 중앙에 위치
  const screenWidth = window.innerWidth
  const screenHeight = window.innerHeight
  position.value = {
    x: (screenWidth - 200) / 2,
    y: (screenHeight - 150) / 2
  }
})

// 컴포넌트 언마운트 시 정리
onUnmounted(() => {
  if (isRecording.value) {
    stopRecording()
  }
  stopDrag()
})
</script>

<style scoped>
.audio-recorder-modal {
  position: fixed;
  width: 200px;
  border-radius: 12px;
  color: white;
  z-index: 1000;
  user-select: none;
  cursor: move;
}

.modal-content {
  padding: 16px;
}

.recorder-controls {
  display: flex;
  justify-content: center;
  margin-bottom: 12px;
}

.record-btn {
  padding: 10px 20px;
  border: none;
  border-radius: 8px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.3s ease;
  min-width: 100px;
}

.start-btn {
  background: linear-gradient(135deg, #10b981, #059669);
  color: white;
}

.start-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(16, 185, 129, 0.3);
}

.stop-btn {
  background: linear-gradient(135deg, #ef4444, #dc2626);
  color: white;
}

.stop-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 15px rgba(239, 68, 68, 0.3);
}

.recording-status {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.status-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 12px;
}

.recording-dot {
  width: 6px;
  height: 6px;
  background: #ef4444;
  border-radius: 50%;
  animation: pulse 1s infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.5; }
}

.recording-time {
  font-family: monospace;
  font-size: 16px;
  font-weight: 600;
}

.chunk-info {
  font-size: 11px;
  opacity: 0.8;
}

.upload-status {
  margin-top: 8px;
}

.status-message {
  font-size: 12px;
  margin-bottom: 6px;
  text-align: center;
}

.status-message.uploading {
  color: #fbbf24;
}

.status-message.success {
  color: #10b981;
}

.status-message.error {
  color: #ef4444;
}

.progress-bar {
  width: 100%;
  height: 3px;
  background: rgba(255, 255, 255, 0.2);
  border-radius: 2px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #10b981, #059669);
  transition: width 0.3s ease;
}

/* 드래그 중일 때 스타일 */
.audio-recorder-modal:active {
  cursor: grabbing;
}

/* 모바일 터치 지원 */
@media (max-width: 768px) {
  .audio-recorder-modal {
    width: 180px;
  }
}
</style>
