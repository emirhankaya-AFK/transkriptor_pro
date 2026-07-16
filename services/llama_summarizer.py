"""Coherent local summaries via a GPU-backed llama.cpp server."""

import logging
import hashlib
import os
import re
import subprocess
import threading
import time
from pathlib import Path

import requests
from langdetect import detect

from transkriptor_pro.config import Config

logger = logging.getLogger(__name__)
_start_lock = threading.Lock()
_process = None
_evidence_lock = threading.Lock()
_evidence_cache = {}


def _server_ready():
    try:
        response = requests.get(f"{Config.LLAMA_SUMMARY_URL}/health", timeout=2)
        return response.status_code == 200
    except requests.RequestException:
        return False


def _find_server_binary():
    package_root = Path(os.environ.get("LOCALAPPDATA", "")) / "Microsoft" / "WinGet" / "Packages"
    matches = list(package_root.glob("ggml.llamacpp_*/llama-server.exe"))
    return str(matches[0]) if matches else None


def _ensure_server(timeout=180):
    global _process
    if _server_ready():
        return True

    with _start_lock:
        if _server_ready():
            return True
        binary = _find_server_binary()
        if not binary:
            logger.error("llama-server.exe bulunamadi")
            return False
        if not Path(Config.LLAMA_MODEL_PATH).is_file():
            logger.error("Yerel GGUF modeli bulunamadi: %s", Config.LLAMA_MODEL_PATH)
            return False

        creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        _process = subprocess.Popen(
            [
                binary,
                "-m", Config.LLAMA_MODEL_PATH,
                "--host", "127.0.0.1",
                "--port", "8081",
                "-ngl", "99",
                "-c", "4096",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=creation_flags,
        )

    deadline = time.time() + timeout
    while time.time() < deadline:
        if _server_ready():
            return True
        if _process and _process.poll() is not None:
            return False
        time.sleep(2)
    return False


def _source_text(snippets):
    return " ".join(
        re.sub(r"\s+", " ", str(item.get("text", ""))).strip()
        for item in snippets
        if str(item.get("text", "")).strip()
    ).strip()


def _chat(prompt, max_tokens, system_message=None):
    response = requests.post(
        f"{Config.LLAMA_SUMMARY_URL}/v1/chat/completions",
        json={
            "model": "local-summary",
            "messages": [
                {
                    "role": "system",
                    "content": system_message or (
                        "You are a precise summarization editor. Follow formatting instructions "
                        "exactly, never invent facts, and always write the final answer in Turkish."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.0,
            "top_p": 0.85,
            "max_tokens": max_tokens,
        },
        timeout=180,
    )
    response.raise_for_status()
    return response.json()["choices"][0]["message"]["content"].strip()


def _split_source(source, target_size=3200, max_chunks=6):
    chunk_count = min(max_chunks, max(1, (len(source) + target_size - 1) // target_size))
    chunk_size = (len(source) + chunk_count - 1) // chunk_count
    chunks = []
    for index in range(chunk_count):
        start = index * chunk_size
        chunk = source[start:start + chunk_size]
        if start:
            chunk = chunk.split(" ", 1)[-1]
        if start + chunk_size < len(source):
            chunk = chunk.rsplit(" ", 1)[0]
        if chunk.strip():
            chunks.append(chunk.strip())
    return chunks


def _extract_evidence(source):
    """Map long transcript sections to a reusable, source-grounded fact sheet."""
    cache_key = hashlib.sha256(source.encode("utf-8")).hexdigest()
    with _evidence_lock:
        cached = _evidence_cache.get(cache_key)
    if cached:
        return cached

    chunks = _split_source(source)
    if len(chunks) == 1:
        evidence = chunks[0]
    else:
        points = []
        for index, chunk in enumerate(chunks, start=1):
            prompt = f"""This is section {index} of {len(chunks)} from a video transcript.
Extract exactly three factual core points from this section.
Write exactly three short bullet lines in clear English, with no title or introduction.
Ignore ads, greetings, repetition, and broken translation fragments.
Do not infer or add any fact, person, number, or claim absent from the source.

SOURCE SECTION:
{chunk}
"""
            point = _chat(
                prompt,
                150,
                system_message="Extract only source-grounded facts. Write in clear English only.",
            )
            if point:
                points.append(f"Bölüm {index}: {point}")
        evidence = "\n".join(points)

    with _evidence_lock:
        if len(_evidence_cache) >= 16:
            _evidence_cache.pop(next(iter(_evidence_cache)))
        _evidence_cache[cache_key] = evidence
    return evidence


def _truncate_clean(text, max_chars):
    if len(text) <= max_chars:
        return text
    candidate = text[:max_chars]
    endings = [candidate.rfind(mark) for mark in ".!?"]
    last_ending = max(endings)
    if last_ending >= int(max_chars * 0.6):
        return candidate[:last_ending + 1].strip()
    return candidate.rsplit(" ", 1)[0].rstrip(" ,;:") + "."


def _translate_summary(text):
    """Translate only the final compact summary; no API key or paid quota."""
    try:
        response = requests.post(
            "https://translate.googleapis.com/translate_a/single",
            data={
                "client": "gtx",
                "sl": "en",
                "tl": "tr",
                "dt": "t",
                "q": text,
            },
            timeout=30,
        )
        response.raise_for_status()
        return "".join(
            part[0] for part in response.json()[0] if part and part[0]
        ).strip()
    except Exception:
        logger.exception("Nihai ozet Turkceye cevrilemedi")
        return ""


def _validate(summary, source, detailed=False):
    if len(summary) < 120:
        return False
    lowered = summary.lower()
    banned = (
        "gerçekten de, ifadeyi",
        "işte genellikle kullanılan metni",
        "kaynak metin:",
        "sistem mesajı",
        "konuşmak istiyorum",
        "anlatım yapacağım",
    )
    if any(item in lowered for item in banned):
        return False
    if not detailed:
        if any(mark in summary for mark in ("#", "**", "- ", "1. ", "2. ")):
            return False
        sentence_count = len(re.findall(r"[.!?](?:\s|$)", summary))
        if sentence_count < 2 or sentence_count > 6:
            return False

    def normalized_numbers(text):
        return {
            value.replace(",", ".").replace("%", "")
            for value in re.findall(r"%?\d+(?:[.,]\d+)?", text)
        }

    source_numbers = normalized_numbers(source)
    output_numbers = normalized_numbers(summary)
    if output_numbers - source_numbers:
        return False

    # Five-letter prefixes provide a lightweight Turkish morphology check:
    # "milyarder" and "milyarderlerin" count as the same supported concept.
    try:
        source_language = detect(source[:10000])
    except Exception:
        source_language = ""
    if source_language == "tr":
        source_words = {
            word[:5] for word in re.findall(r"[a-zçğıöşü]{5,}", source.lower())
        }
        output_words = {
            word[:5] for word in re.findall(r"[a-zçğıöşü]{5,}", lowered)
        }
        if output_words and len(output_words & source_words) / len(output_words) < 0.22:
            return False
    return True


def generate_llama_summary(snippets, max_chars=900, detailed=False):
    source = _source_text(snippets)
    if len(source) < 80 or not _ensure_server():
        return ""

    if detailed:
        format_rule = (
            "Write 3-5 compact sections with short Markdown headings. Under each heading, "
            "explain the core claim, important details, and cause-effect relationship. "
            "Keep the entire response under 350 words."
        )
        token_limit = 500
    else:
        format_rule = (
            "Write exactly one paragraph of 4 connected English sentences and keep it under "
            "130 words. No title, "
            "no Markdown, no bullets, and no numbered rules. Explain the main idea, "
            "its key reasons, and the overall conclusion."
        )
        token_limit = 300

    evidence = _extract_evidence(source)
    prompt = f"""Synthesize the verified section notes below into a natural English summary.

Rules:
- Do not copy or list the source sentences; explain their combined meaning in your own words.
- Cover the shared main topic, key ideas, cause-effect relationships, and conclusion across ALL sections.
- Do not walk through sections in order and do not output a list of rules.
- Never add a person, organization, event, number, ratio, or claim absent from the notes.
- Ignore ads, greetings, repeated phrases, and broken translation fragments.
- {format_rule}
- Focus on the concepts; do not use named examples in the short summary.
- Output only the final English summary.

VERIFIED SECTION NOTES:
{evidence}
"""
    english_summary = _chat(
        prompt,
        token_limit,
        system_message=(
            "You are a precise English summarization editor. Use only source-grounded "
            "facts and follow the requested format exactly."
        ),
    )
    english_summary = re.sub(
        r"^(summary|final summary)\s*:\s*",
        "",
        english_summary,
        flags=re.IGNORECASE,
    )
    if not _validate(english_summary, source, detailed=detailed):
        logger.warning("Yerel LLM'nin Ingilizce ozeti kalite kontrolunden gecemedi")
        return ""

    summary = _translate_summary(english_summary)
    if not summary:
        return ""
    if not detailed:
        summary = re.sub(r"\s+", " ", summary).strip()
    summary = _truncate_clean(summary, max_chars)
    if not _validate(summary, source, detailed=detailed):
        logger.warning("Yerel LLM ozeti kalite kontrolunden gecemedi")
        return ""
    return summary
