import os
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent

from dotenv import load_dotenv

# Always load the environment file next to this module, regardless of cwd.
load_dotenv(BASE_DIR / ".env")

class Config:
    # API Keys
    OCR_SPACE_KEY = os.environ.get("OCR_SPACE_KEY", "").strip()

    # Optional trusted proxy. Never use browser cookies with public proxies.
    TRANSCRIPT_PROXY_URL = os.environ.get("TRANSCRIPT_PROXY_URL", "").strip()
    
    # Database
    DATABASE_PATH = str(BASE_DIR / "transcripts.db")
    
    # Server configuration
    HOST = "127.0.0.1"
    PORT = 5000
    DEBUG = False
    
    # Request timeouts (seconds)
    YOUTUBE_TIMEOUT = 10
    OCR_SPACE_TIMEOUT = 30

    # Local abstractive Turkish summarizer. No external AI API is used.
    ABSTRACTIVE_SUMMARY_ENABLED = os.environ.get(
        "ABSTRACTIVE_SUMMARY_ENABLED", "true"
    ).strip().lower() in {"1", "true", "yes", "on"}
    ABSTRACTIVE_MODEL = os.environ.get(
        "ABSTRACTIVE_MODEL",
        "ozcangundes/mt5-small-turkish-summarization",
    ).strip()
    LLAMA_SUMMARY_URL = os.environ.get(
        "LLAMA_SUMMARY_URL",
        "http://127.0.0.1:8081",
    ).rstrip('/')
    LLAMA_SUMMARY_MODEL = os.environ.get(
        "LLAMA_SUMMARY_MODEL",
        "bartowski/Qwen2.5-3B-Instruct-GGUF:Q4_K_M",
    ).strip()
    LLAMA_MODEL_PATH = os.environ.get(
        "LLAMA_MODEL_PATH",
        str(BASE_DIR / "models" / "Qwen2.5-7B-Instruct-Q4_K_M.gguf"),
    ).strip()
