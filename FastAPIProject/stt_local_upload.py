import os, sys, json, time, argparse, requests
from dotenv import load_dotenv

def _normalize_base_url(url: str) -> str:
    if not url:
        raise RuntimeError("CLOVA_INVOKE_URL 이 비었습니다.")
    url = url.strip().rstrip("/")
    for suffix in ("/recognizer/upload", "/recognizer/url", "/recognizer"):
        if url.endswith(suffix):
            url = url[: -len(suffix)]
            break
    return url

def _post_upload(endpoint: str, secret: str, file_path: str, body: dict):
    headers = {
        "Accept": "application/json;UTF-8",
        "X-CLOVASPEECH-API-KEY": secret,
    }
    with open(file_path, "rb") as f:
        files = {
            "media": f,
            "params": (None, json.dumps(body, ensure_ascii=False).encode("UTF-8"), "application/json"),
        }
        return requests.post(endpoint, headers=headers, files=files, timeout=600)

def run(file_path: str, env_path: str, completion: str):
    # 1) .env 로드
    for p in [env_path, ".env"]:
        if p and os.path.exists(p):
            load_dotenv(p)
            print(f"🧩 .env 로드: {os.path.abspath(p)}")
            break

    raw_url = os.getenv("CLOVA_INVOKE_URL", "")
    secret  = os.getenv("CLOVA_SECRET_KEY", "")
    base_url = _normalize_base_url(raw_url)
    endpoint = base_url + "/recognizer/upload"

    print("🌐 BASE_URL:", base_url)
    print("🔚 ENDPOINT:", endpoint)
    print("🔑 SECRET_KEY head:", (secret[:6] + "…") if secret else "None")
    try:
        part = base_url.split("/external/v1/")[1]
        app_id, domain_id = part.split("/")[0], part.split("/")[1]
        print(f"🔎 app_id={app_id}, domain_id={domain_id}")
    except Exception:
        pass

    if not secret:
        raise RuntimeError("CLOVA_SECRET_KEY 가 비었습니다.")
    if not os.path.isfile(file_path):
        raise RuntimeError(f"파일 없음: {file_path}")

    # 2) 요청 바디 (A 방법: 화자 인식/워드 얼라인먼트 OFF로 고정)
    request_body = {
        "language": "ko-KR",
        "completion": completion,   # "sync" | "async"
        "callback": None,
        "userdata": None,
        "wordAlignment": False,          # CHANGED
        "fullText": True,
        "forbiddens": None,
        "boostings": None,
        "diarization": {"enable": False},# CHANGED
        "sed": None,
    }

    # 3) 재현용 curl
    safe_path = file_path.replace("\\", "/")
    print("🐚 curl 재현:")
    print(
        'curl -X POST "{url}" '
        '-H "X-CLOVASPEECH-API-KEY: {key}" '
        '-H "Accept: application/json;UTF-8" '
        '-F "media=@{path}" '
        '-F "params={params};type=application/json"'
        .format(url=endpoint, key=(secret[:6] + "…"),
                path=safe_path, params=json.dumps(request_body, ensure_ascii=False))
    )

    # 4) 호출
    started = time.time()
    resp = _post_upload(endpoint, secret, file_path, request_body)
    took = time.time() - started
    ctype = resp.headers.get("content-type", "")
    print(f"✅ 응답: status={resp.status_code}, content-type={ctype}, took={took:.2f}s")
    try:
        print("🔁 resp headers:", dict(resp.headers))
    except Exception:
        pass
    preview = (resp.text or "")[:300].replace("\n", " ")
    print("📝 응답 미리보기:", preview)

    # 5) 덤프 저장
    out_dir = os.path.dirname(os.path.abspath(file_path))
    dump_path = os.path.join(out_dir, "stt_response_debug.txt")
    with open(dump_path, "w", encoding="utf-8") as fw:
        fw.write(f"HTTP {resp.status_code}\nContent-Type: {ctype}\nTook: {took:.2f}s\n\n")
        fw.write(resp.text or "")
    print("💾 응답 덤프:", dump_path)

    # 6) 에러 처리
    if resp.status_code == 404:
        print("❗ 404(UNKNOWN)= 경로/도메인/키 짝 문제.")
        sys.exit(1)
    if resp.status_code in (401, 403):
        print("❗ 키/권한 오류.")
        sys.exit(1)
    if resp.status_code == 415:
        print("❗ 전송 형식 오류.")
        sys.exit(1)
    if resp.status_code == 400:
        print("❗ 400 잘못된 요청 파라미터(문구 확인).")
        sys.exit(1)
    if resp.status_code != 200:
        print("❗ 호출 실패:", resp.status_code)
        sys.exit(1)

    # 7) transcript 저장
    try:
        data = resp.json()
        text = data.get("text") or data.get("result") or json.dumps(data, ensure_ascii=False)
    except Exception:
        text = resp.text
    text = (text or "").strip()

    tr_path = os.path.join(out_dir, "transcript.txt")
    with open(tr_path, "w", encoding="utf-8") as fw:
        fw.write(text)
    print("✅ transcript 저장:", tr_path)
    print("🎉 완료")

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--file", required=True, help="예: C:/.../FastAPIProject/1/Merge__1.wav")
    ap.add_argument("--env", default=os.path.join(os.path.dirname(__file__), "../backend/.env"))
    ap.add_argument("--completion", default="sync", choices=["sync", "async"])
    args = ap.parse_args()
    run(args.file, args.env, args.completion)
