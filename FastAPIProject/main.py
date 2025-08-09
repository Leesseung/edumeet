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

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 필요하면 특정 origin으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 요청 Body 스키마 정의
class MergeRequest(BaseModel):
    class_dir: str                    # 오디오 파일들이 들어있는 디렉토리 경로
    pattern: str | None = "audio_*.wav"  # 병합할 wav 파일 패턴 (기본값)
    out: str | None = "merged.wav"       # 병합 후 저장할 파일 이름 (기본값)


@app.post("/merge")
def merge_audio(req: MergeRequest):
    # 경로 검증만 일단 하고, 병합은 다음 단계에서 붙일게
    dir_path = os.path.normpath(req.class_dir)

    if not os.path.isdir(dir_path):
        raise HTTPException(status_code=400, detail=f"Directory not found: {dir_path}")

    # TODO: 여기에서 실제 병합 로직 호출 (다음 단계에서 구현)
    # merged_path = do_merge(dir_path, req.pattern, req.out)

    # 스텁 응답
    return {
        "message": "merge request receive",
        "class_dir": dir_path,
        "pattern": req.pattern,
        "out": req.out,
        # "merged_path": merged_path,
    }