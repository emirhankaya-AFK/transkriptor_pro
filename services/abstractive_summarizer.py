"""Local Turkish abstractive summarization.

The model is downloaded from Hugging Face on first use and runs locally.
There is no Gemini, translation API, or other paid inference service here.
"""

import logging
import re
import threading

import torch
from transkriptor_pro.config import Config

logger = logging.getLogger(__name__)
_load_lock = threading.Lock()
_tokenizer = None
_model = None
_device = torch.device("cuda" if torch.cuda.is_available() else "cpu")


def _load_model():
    global _tokenizer, _model
    if _tokenizer is not None and _model is not None:
        return _tokenizer, _model

    with _load_lock:
        if _tokenizer is not None and _model is not None:
            return _tokenizer, _model

        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

        logger.info("Yerel abstractive model yukleniyor: %s", Config.ABSTRACTIVE_MODEL)
        _tokenizer = AutoTokenizer.from_pretrained(Config.ABSTRACTIVE_MODEL)
        # Prefer safetensors so current PyTorch security checks do not reject
        # the legacy pytorch_model.bin file shipped by some model revisions.
        _model = AutoModelForSeq2SeqLM.from_pretrained(
            Config.ABSTRACTIVE_MODEL,
            use_safetensors=True,
        )
        _model.to(_device)
        _model.eval()
        logger.info("Yerel abstractive model hazir. Cihaz: %s", _device)
    return _tokenizer, _model


def _plain_text(snippets):
    return " ".join(
        re.sub(r"\s+", " ", str(item.get("text", ""))).strip()
        for item in snippets
        if str(item.get("text", "")).strip()
    ).strip()


def _chunks(text, max_chars=2600):
    words = text.split()
    chunks = []
    current = []
    size = 0
    for word in words:
        if current and size + len(word) + 1 > max_chars:
            chunks.append(" ".join(current))
            current = []
            size = 0
        current.append(word)
        size += len(word) + 1
    if current:
        chunks.append(" ".join(current))
    return chunks


def _generate(text, max_new_tokens):
    tokenizer, model = _load_model()
    encoded = tokenizer(
        text,
        max_length=784,
        truncation=True,
        padding=True,
        return_tensors="pt",
    )
    encoded = {key: value.to(_device) for key, value in encoded.items()}
    with torch.inference_mode():
        generated = model.generate(
            **encoded,
            num_beams=2,
            max_new_tokens=max_new_tokens,
            min_new_tokens=20,
            no_repeat_ngram_size=3,
            repetition_penalty=1.6,
            length_penalty=1.0,
            early_stopping=True,
        )
    return tokenizer.decode(
        generated[0],
        skip_special_tokens=True,
        clean_up_tokenization_spaces=True,
    ).strip()


def generate_abstractive_summary(snippets, max_chars=900):
    """Create a coherent Turkish summary by rewriting transcript content."""
    text = _plain_text(snippets)
    if len(text) < 80:
        return ""

    # One generation pass is deliberate: mT5-small is accurate but expensive
    # on CPU. Keep a broad context window and let the tokenizer truncate the
    # least useful tail rather than making several slow model calls per video.
    context = text[:9000]
    result = _generate(context, 110 if max_chars <= 1000 else 170)
    result = re.sub(r"\s+", " ", result).strip()
    if len(result) > max_chars:
        result = result[:max_chars].rsplit(" ", 1)[0].rstrip(" ,;:") + "."
    if result and result[-1] not in ".!?":
        result += "."
    return result
