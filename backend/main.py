"""
PigeonBrief FastAPI 백엔드
실행: .venv/bin/uvicorn backend.main:app --host 0.0.0.0 --port 8000
"""
import os
from pathlib import Path

# .env 로드 (반드시 backend.* import 보다 먼저 실행되어야 함 — auth.py 등이
# 모듈 로드 시점에 os.environ을 읽을 가능성이 있기 때문)
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.database import init_db
from backend.routers import settings, articles

app = FastAPI(title="PigeonBrief API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://pigeonbrief.com",
        "https://www.pigeonbrief.com",
        "https://pigeonbrief.vercel.app",
        "http://localhost:3000",  # 로컬 테스트용
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/health")
def health():
    return {"status": "ok"}


app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(articles.router, prefix="/api/articles", tags=["articles"])
