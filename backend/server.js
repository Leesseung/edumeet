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

app.post("/api/class/:classId/start-recording", (req, res) => {
  const { classId } = req.params;
  console.log("classID 입니다 ", classId);
  const classDir = path.join(AUDIO_BASE_PATH, classId);
  console.log("classDir 입니다 : ", classDir);
  fs.mkdirSync(classDir, { recursive: true });
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

  if (!file) {
    return res.status(400).json({ message: 'No audio file uploaded.' });
  }

  console.log(`✅ 저장됨: /audio/${classId}/${file.filename}`);
  res.status(200).json({ message: 'Chunk saved successfully.', filename: file.filename });
});

app.post("/api/class/:classId/stop-recording", (req, res) => {
  const { classId } = req.params;
  const { totalChunks } = req.body;

  const pyPath = path.join(__dirname, "test_nodejs_api.py");
  const classDir = path.join(AUDIO_BASE_PATH, classId);
  const command = `python3 ${pyPath} ${classDir} ${totalChunks}`;

  exec(command, (err, stdout, stderr) => {
    if (err) {
      console.error("병합 실패:", stderr);
      return res.status(500).json({ error: "오디오 병합 실패" });
    }
    console.log("병합 결과:", stdout);
    res.status(200).json({ message: "병합 성공", result: stdout });
  });
});





app.listen(PORT, () => {
  console.log(`🚀 Server running at http://localhost:${PORT}`);
});