# main.py
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
import os, re, glob, wave, traceback, subprocess, requests, time, json
from dotenv import load_dotenv
from openai import OpenAI
from fpdf import FPDF
app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

HERE = os.path.dirname(os.path.abspath(__file__))
BASE_AUDIO_DIR = os.environ.get(
    "AUDIO_BASE_DIR",
    os.path.normpath(os.path.join(HERE, "..", "backend", "audio"))
)
MERGE_OUT_DIR = os.environ.get(
    "MERGE_OUT_DIR",
    os.path.normpath(os.path.join(HERE, "..", "FastAPIProject"))
)
os.makedirs(MERGE_OUT_DIR, exist_ok=True)

def _numeric_key(path: str) -> int:
    """audio_12.wav -> 12 정렬키"""
    name = os.path.basename(path)
    m = re.search(r"(\d+)", name)
    return int(m.group(1)) if m else 0

def _peek_header(path: str, n=16) -> bytes:
    try:
        with open(path, "rb") as f:
            return f.read(n)
    except Exception:
        return b""


def _is_riff(path: str) -> bool:
    try:
        with open(path, "rb") as f:
            return f.read(4) == b"RIFF"
    except Exception:
        return False


def ensure_wav(file_path: str) -> str:
    # 이미 WAV(RIFF)이면 그대로 사용
    try:
        with open(file_path, 'rb') as f:
            if f.read(4) == b'RIFF':
                return file_path
    except Exception:
        pass

    # 변환 경로
    base, _ = os.path.splitext(file_path)
    wav_path = base + ".conv.wav"

    # ffmpeg 변환 (16kHz, mono, PCM 16-bit)
    cmd = ["ffmpeg", "-y", "-i", file_path, "-ar", "16000", "-ac", "1", "-acodec", "pcm_s16le", wav_path]
    subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # 변환 결과 검증
    with open(wav_path, 'rb') as f:
        if f.read(4) != b'RIFF':
            raise RuntimeError(f"ffmpeg 변환 후에도 WAV가 아닙니다: {wav_path}")

    return wav_path

# def _is_riff_wav(path: str) -> bool:
#     try:
#         with open(path, "rb") as f:
#             return f.read(4) == b"RIFF"
#     except:
#         return False

def merge_wav_files(input_files, out_path):
    """
    wave 모듈로 WAV 병합 (메모리 절약을 위해 블록 단위로 읽어서 씀)
    모든 입력 파일의 (channels, sampwidth, framerate, comptype) 동일해야 함
    """
    if not input_files:
        raise ValueError("병합할 WAV 파일이 없습니다.")

    # # 1) 첫 파일의 파라미터를 기준으로 고정
    # with wave.open(input_files[0], "rb") as w0:
    #     nchannels = w0.getnchannels()
    #     sampwidth = w0.getsampwidth()
    #     framerate = w0.getframerate()
    #     comptype = w0.getcomptype()
    #     compname = w0.getcompname()

    print("[merge] input_files:")
    for p in input_files:
        size = os.path.getsize(p) if os.path.exists(p) else -1
        hdr = _peek_header(p, 12)
        print(f"  - {p} (size={size} bytes, header={hdr})")

     # 1) 기준 파라미터 확보 (첫 파일 오픈에서 에러가 나면 WAV가 아닐 가능성 큼)
    try:
        with wave.open(input_files[0], "rb") as w0:
            nchannels = w0.getnchannels()
            sampwidth = w0.getsampwidth()
            framerate = w0.getframerate()
            comptype = w0.getcomptype()
            compname = w0.getcompname()
            print(f"[merge] base params: ch={nchannels}, width={sampwidth}, rate={framerate}, comp={comptype}")
    except wave.Error as we:
        # RIFF가 아닌 경우 대부분 여기서 터짐
        raise HTTPException(status_code=415, detail=f"첫 파일이 WAV가 아닙니다: {input_files[0]} ({we})")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"첫 파일 오픈 중 예외: {input_files[0]} ({e})")



    # # 2) 출력 파일 오픈
    # with wave.open(out_path, "wb") as out:
    #     out.setnchannels(nchannels)
    #     out.setsampwidth(sampwidth)
    #     out.setframerate(framerate)
    #     out.setcomptype(comptype, compname)

    #     # 3) 순서대로 이어붙이기
    #     for fpath in input_files:
    #         # WAV 헤더(=RIFF) 검사
    #         if not _is_riff_wav(fpath):
    #             raise ValueError(f"RIFF가 아닌 파일: {os.path.basename(fpath)} (진짜 WAV인지 확인)")

    #         with wave.open(fpath, "rb") as w:
    #             # 파라미터 일치 검사
    #             if (w.getnchannels() != nchannels or
    #                 w.getsampwidth() != sampwidth or
    #                 w.getframerate() != framerate or
    #                 w.getcomptype() != comptype):
    #                 raise ValueError(
    #                     f"오디오 파라미터 불일치: {os.path.basename(fpath)} "
    #                     f"(ch={w.getnchannels()}, width={w.getsampwidth()}, rate={w.getframerate()}, comp={w.getcomptype()}) "
    #                     f"vs 기준(ch={nchannels}, width={sampwidth}, rate={framerate}, comp={comptype})"
    #                 )

    #             # 블록 단위로 프레임 복사
    #             block_frames = 64 * 1024  # 프레임 수
    #             remaining = w.getnframes()
    #             while remaining > 0:
    #                 chunk = min(remaining, block_frames)
    #                 data = w.readframes(chunk)
    #                 out.writeframes(data)
    #                 remaining -= chunk

    # 2) 출력 파일 생성
    try:
        with wave.open(out_path, "wb") as out:
            out.setnchannels(nchannels)
            out.setsampwidth(sampwidth)
            out.setframerate(framerate)
            out.setcomptype(comptype, compname)

            # 3) 순서대로 이어붙이기
            for fpath in input_files:
                # 빠른 헤더 체크
                if not _is_riff(fpath):
                    raise HTTPException(status_code=415, detail=f"RIFF(WAV)가 아닌 파일: {fpath}")

                try:
                    with wave.open(fpath, "rb") as w:
                        # 파라미터 일치 검사
                        if (w.getnchannels() != nchannels or
                            w.getsampwidth() != sampwidth or
                            w.getframerate() != framerate or
                            w.getcomptype() != comptype):
                            raise HTTPException(
                                status_code=415,
                                detail=(f"오디오 파라미터 불일치: {os.path.basename(fpath)} "
                                        f"(ch={w.getnchannels()}, width={w.getsampwidth()}, "
                                        f"rate={w.getframerate()}, comp={w.getcomptype()}) "
                                        f"vs 기준(ch={nchannels}, width={sampwidth}, "
                                        f"rate={framerate}, comp={comptype})")
                            )

                        # 블록 단위 복사 (frame 단위)
                        block_frames = 64 * 1024
                        remaining = w.getnframes()
                        while remaining > 0:
                            chunk = min(remaining, block_frames)
                            data = w.readframes(chunk)
                            out.writeframes(data)
                            remaining -= chunk
                except wave.Error as we:
                    # 특정 파일에서만 WAV 파싱 오류
                    raise HTTPException(status_code=415, detail=f"WAV 파싱 실패: {fpath} ({we})")
                except HTTPException:
                    # 위에서 상태코드 정해 올린 경우 그대로 던짐
                    raise
                except Exception as e:
                    traceback.print_exc()
                    raise HTTPException(status_code=500, detail=f"파일 처리 중 예외: {fpath} ({e})")
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"출력 파일 작성 중 예외: {out_path} ({e})")


    return out_path


def _normalize_base_url(url: str) -> str:
    """
    .env에는 base만 있어도 되고, 만약 /recognizer, /recognizer/url, /recognizer/upload가 붙어있으면 떼어낸다.
    """
    if not url:
        raise HTTPException(status_code=500, detail="CLOVA_INVOKE_URL 이 비었습니다.")
    url = url.strip().rstrip("/")
    for suf in ("/recognizer/upload", "/recognizer/url", "/recognizer"):
        if url.endswith(suf):
            url = url[: -len(suf)]
            break
    return url


def Start_STT(out_path: str, class_id: str) -> dict:
    print(f"▶️ [STT] 시작: {out_path} (class_id={class_id})")

    # ../backend/.env 로드
    env_path = os.path.join(os.path.dirname(__file__), "../backend/.env")
    print(f"🧩 env 경로: {env_path} exists= {os.path.exists(env_path)}")
    load_dotenv(env_path)

    raw_url = os.getenv("CLOVA_INVOKE_URL", "")
    secret  = os.getenv("CLOVA_SECRET_KEY", "")

    # BASE URL 정규화 → /recognizer/upload 붙여 사용
    try:
        base_url = _normalize_base_url(raw_url)
    except HTTPException as he:
        return {"ok": False, "detail": he.detail}

    endpoint = base_url + "/recognizer/upload"
    print("🌐 BASE_URL:", base_url)
    print("🔚 ENDPOINT:", endpoint)
    print("🔑 SECRET_KEY head:", (secret[:6] + "…") if secret else "None")
    print("🌐 BASE_URL raw repr:", repr(base_url))
    try:
        part = base_url.split("/external/v1/")[1]
        app_id, domain_id = part.split("/")[0], part.split("/")[1]
        print(f"🔎 app_id={app_id}, domain_id={domain_id}")
    except Exception:
        pass

    if not secret:
        return {"ok": False, "detail": "CLOVA_SECRET_KEY 가 비어 있습니다."}
    if not os.path.isfile(out_path):
        return {"ok": False, "detail": f"파일 없음: {out_path}"}

    # 파일 헤더/크기 로그
    hdr12 = _peek_header(out_path, 12)
    size = os.path.getsize(out_path)
    print(f"📦 업로드 파일 크기: {size} bytes, 헤더: {hdr12!r}")

    # A 방법: 화자 인식/워드 얼라인먼트 OFF
    request_body = {
        "language": "ko-KR",
        "completion": "sync",
        "callback": None,
        "userdata": None,
        "wordAlignment": False,           # OFF
        "fullText": True,
        "forbiddens": None,
        "boostings": None,
        "diarization": {"enable": False}, # OFF
        "sed": None,
    }

    headers = {
        "Accept": "application/json;UTF-8",
        "X-CLOVASPEECH-API-KEY": secret,
    }

    # 재현용 curl
    safe_path = out_path.replace("\\", "/")
    print("🐚 curl 예시:")
    print(
        'curl -X POST "{url}" '
        '-H "X-CLOVASPEECH-API-KEY: {key}" '
        '-H "Accept: application/json;UTF-8" '
        '-F "media=@{path}" '
        '-F "params={params};type=application/json"'
        .format(url=endpoint, key=(secret[:6] + "…"),
                path=safe_path, params=json.dumps(request_body, ensure_ascii=False))
    )

    started = time.time()
    try:
        with open(out_path, "rb") as f:
            files = {
                # 공식 예제와 동일: 파일 핸들을 그대로 전달
                "media": f,
                "params": (None, json.dumps(request_body, ensure_ascii=False).encode("UTF-8"), "application/json"),
            }
            resp = requests.post(endpoint, headers=headers, files=files, timeout=600)
    except requests.Timeout as e:
        print("⏱️ 타임아웃:", e)
        return {"ok": False, "detail": f"요청 타임아웃: {e}"}
    except Exception as e:
        print("⚠️ 요청 예외:", e)
        return {"ok": False, "detail": f"요청 실패: {e}"}

    took = time.time() - started
    ctype = resp.headers.get("content-type", "")
    print(f"✅ 응답: status={resp.status_code}, content-type={ctype}, took={took:.2f}s")
    try:
        print("🔁 resp headers:", dict(resp.headers))
    except Exception:
        pass
    preview = (resp.text or "")[:300].replace("\n", " ")
    print("📝 응답 미리보기:", preview)

    # 응답 덤프
    transcript_dir = os.path.dirname(out_path)
    debug_path = os.path.join(transcript_dir, "stt_response_debug.txt")
    try:
        with open(debug_path, "w", encoding="utf-8") as fw:
            fw.write(f"HTTP {resp.status_code}\nContent-Type: {ctype}\nTook: {took:.2f}s\n\n")
            fw.write(resp.text or "")
        print("💾 응답 덤프:", debug_path)
    except Exception as e:
        print("⚠️ 응답 덤프 저장 실패:", e)

    # 에러 처리 (메시지 보강)
    if resp.status_code == 404:
        hint = "404=경로 미매핑. 같은 도메인의 Invoke URL/Secret Key인지, URL 끝 경로(/recognizer/upload) 확인."
        return {"ok": False, "detail": f"HTTP 404: {resp.text} | HINT: {hint}"}
    if resp.status_code in (401, 403):
        return {"ok": False, "detail": "키/권한 오류. Secret Key/도메인 짝을 확인하세요."}
    if resp.status_code == 415:
        return {"ok": False, "detail": "전송 형식 오류. multipart(media/params) 구성 확인."}
    if resp.status_code == 400:
        return {"ok": False, "detail": f"요청 파라미터 오류: {resp.text}"}  # (이전 'speaker detect is off' 같은 케이스)
    if resp.status_code != 200:
        return {"ok": False, "detail": f"HTTP {resp.status_code}: {resp.text}"}

    # 결과 저장
    try:
        data = resp.json()
        text = data.get("text") or data.get("result") or json.dumps(data, ensure_ascii=False)
    except Exception:
        text = resp.text
    text = (text or "").strip()

    transcript_path = os.path.join(transcript_dir, "transcript.txt")
    try:
        with open(transcript_path, "w", encoding="utf-8") as fw:
            fw.write(text)
        print("✅ transcript 저장:", transcript_path)
    except Exception as e:
        print("⚠️ transcript 저장 실패:", e)
        return {"ok": True, "text": text, "detail": f"저장 실패: {e}"}

    return {"ok": True, "text": text, "transcript_path": transcript_path}






@app.post("/STT/{class_id}")
def merge_audio(class_id: str):
    print("파이썬 merge 합병 처리 -> class_id : ", class_id)
    """
    입력:  BASE_AUDIO_DIR/{class_id}/audio_*.wav (없으면 *.wav)
    출력:  MERGE_OUT_DIR/Merge__{class_id}.wav
    """
    in_dir = os.path.join(BASE_AUDIO_DIR, str(class_id))
    print("in_dir : ", in_dir)
    if not os.path.isdir(in_dir):
        raise HTTPException(status_code=400, detail=f"Directory not found: {in_dir}")



    # 대상 파일 수집
    patterns = [os.path.join(in_dir, "audio_*.wav"), os.path.join(in_dir, "*.wav")]
    candidates = []
    for pat in patterns:
        candidates.extend(glob.glob(pat))
    files = sorted(set(candidates), key=_numeric_key)

    if not files:
        raise HTTPException(status_code=404, detail=f"No WAV files found in {in_dir}")

    
    class_out_dir = os.path.join(MERGE_OUT_DIR, str(class_id))
    os.makedirs(class_out_dir, exist_ok=True)
    out_path = os.path.join(class_out_dir, f"Merge__{class_id}.wav")
    print("out_path : ", out_path)

    try:
        wav_ready = [ensure_wav(p) for p in files]
        
        for p in wav_ready:
            size = os.path.getsize(p)
            with open(p, "rb") as f:
                hdr = f.read(12)
            print(f"  - {p} (size={size}, header={hdr})")  # 여기서는 꼭 b'RIFF'가 찍혀야 함

        merged = merge_wav_files(wav_ready, out_path)
        print("merged => ", merged)
        stt_result = Start_STT(out_path,class_id)
    except ValueError as ve:
        # 포맷/파라미터 문제 등
        raise HTTPException(status_code=415, detail=str(ve))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Merge failed: {e}")

    return {
        "message": "STT success",
        "class_id": class_id,
        "input_dir": in_dir,
        "files_merged": [os.path.basename(f) for f in files],
        "output_path": merged,
        "stt_ok": stt_result.get("ok", False),
        "transcript_path": stt_result.get("transcript_path"),
        "stt_detail": stt_result.get("detail"),
    }
