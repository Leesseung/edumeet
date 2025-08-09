const express = require("express");
const fs = require("fs");
const path = require("path");
const multer = require("multer");
const { exec } = require("child_process");
const bodyParser = require("body-parser");
const cors = require("cors");
require('dotenv').config();

const app = express();
const PORT = process.env.PORT || 3001;
const FASTAPI_URL = process.env.FASTAPI_URL || "http://127.0.0.1:8000/merge";
const recordingState = new Map();

// 환경변수 확인 로그 추가
// console.log('🔥 환경변수 확인:');
// console.log('OPENAI_API_KEY:', process.env.OPENAI_API_KEY ? '설정됨' : '없음');
// console.log('API 키 시작:', process.env.OPENAI_API_KEY ? process.env.OPENAI_API_KEY.substring(0, 10) + '...' : 'None');
// console.log('PORT:', process.env.PORT);

// CORS 및 JSON 파싱 설정
app.use(cors());
app.use(express.json({ limit: '10mb' }));

const AUDIO_BASE_PATH=path.join(__dirname, "audio");


//현재 __dirpath  C:\workspace\fronted\edumeet_frontend\backend    
console.log("현재 __dirpath " , __dirname);
//console.log("현재 AUDIO_BASE_PATH" , AUDIO_BASE_PATH);
// AUDIO_BASE_PATH C:\workspace\fronted\edumeet_frontend\backend\audio

app.post("/api/class/:classId/start-recording", (req, res) => {
  const { classId } = req.params;
  console.log("classID 입니다 ", classId);
  const classDir = path.join(AUDIO_BASE_PATH, classId);
  console.log("classDir 입니다 : ", classDir);
  fs.mkdirSync(classDir, { recursive: true });
  recordingState.set(classId, {recording:true});
  res.status(200).json({ message: "녹음 저장 시작 준비 완료" });
});


const storage = multer.diskStorage({
  destination: function (req, file, cb) {
    const classId = req.params.classId;
    const dir = path.join(__dirname, 'audio', classId);
    
    // 디렉토리 없으면 생성
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }
    cb(null, dir);
  },
  filename: function (req, file, cb) {
    const classId = req.params.classId;
    const dir = path.join(__dirname, 'audio', classId);

    // 현재 저장된 chunk 개수 파악
    const files = fs.readdirSync(dir).filter(f => f.startsWith('audio_') && f.endsWith('.wav'));
    const nextChunk = files.length + 1;
    const filename = `audio_${nextChunk}.wav`;

    cb(null, filename);
  }
});

const upload = multer({ storage: storage });


app.post('/api/class/:classId/update-recording', upload.single('audio'), (req, res) => {
  const classId = req.params.classId;
  const file = req.file;

  const st = recordingState.get(classId);
  if(!st || !st.recording){
    return res.status(423).json({
      message : '문서 요약 작업 중입니다. 더이상 녹화를 시작할 수 없습니다.'
    });
  }


  if (!file) {
    return res.status(400).json({ message: 'No audio file uploaded.' });
  }

  console.log(`✅ 저장됨: /audio/${classId}/${file.filename}`);
  res.status(200).json({ message: 'Chunk saved successfully.', filename: file.filename });
});


app.post("/api/class/:classId/stop-recording", async (req, res) => {
  try{
  
    const { classId } = req.params;

    //const pyPath = path.join(__dirname, "test_nodejs_api.py");
    const classDir = path.join(AUDIO_BASE_PATH, classId);
    //const command = `python3 ${pyPath} ${classDir} ${totalChunks}`;

    // 업로드 차단
    recordingState.set(classId, {recording : false});

    //console.log("pyPath : ", pyPath);
    console.log("[stop-recording] classDir : ",classDir);
    console.log("[stop-recording] sending to FastAPI : " , FASTAPI_URL);
    //console.log("command : ", command);

    // FastAPI로 POST
    const payload = {
      class_dir: classDir,
      // 필요 시 옵션도 보낼 수 있음
      // pattern: "audio_*.wav",
      // out: "merged.wav",
    };

    // fast api 호출
    const resp = await fetch(FASTAPI_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
      // 타임아웃 제어가 필요하면 AbortController 사용 권장
    });

    if (!resp.ok) {
      const text = await resp.text().catch(() => "");
      console.error("FastAPI error:", resp.status, text);
      return res.status(502).json({ error: "FastAPI 요청 실패", detail: text });
    }

    // 3) FastAPI 응답 JSON 파싱
    const data = await resp.json();

    // 4) Vue 응답 전송
    return res.status(202).json({
      message: "처리 시작",
      recordingStopped: true,
      job: data, // {job_id, status, ...}
    });

    // 5) 응답 전송 후 /audio/<classId> 폴더 삭제
    try {
      if (fs.existsSync(classDir)) {
        fs.rmSync(classDir, { recursive: true, force: true });
        console.log(`🗑️  ${classDir} 폴더 삭제 완료`);
      }
    } catch (delErr) {
      console.error(`⚠️  ${classDir} 폴더 삭제 중 오류:`, delErr);
    }

  }catch (e) {
    return res.status(500).json({ error: "서버 내부 오류", detail: String(e) });
  }


});





app.listen(PORT, () => {
  console.log(`🚀 Server running at http://localhost:${PORT}`);
});