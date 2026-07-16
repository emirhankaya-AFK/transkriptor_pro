"""Offline transcript translation with Argos Translate."""

import logging
import threading

import argostranslate.package
import argostranslate.translate
from langdetect import DetectorFactory, detect

logger = logging.getLogger(__name__)
DetectorFactory.seed = 0

SUPPORTED = {"en", "de", "it", "es", "fr", "pt", "nl", "ru", "tr"}
_install_lock = threading.Lock()


def _installed_pair(source, target):
    for language in argostranslate.translate.get_installed_languages():
        if language.code != source:
            continue
        for translation in language.translations_from:
            if translation.to_lang.code == target:
                return translation
    return None


def _ensure_pair(source, target):
    installed = _installed_pair(source, target)
    if installed:
        return installed

    with _install_lock:
        installed = _installed_pair(source, target)
        if installed:
            return installed

        argostranslate.package.update_package_index()
        package = next(
            (
                item
                for item in argostranslate.package.get_available_packages()
                if item.from_code == source and item.to_code == target
            ),
            None,
        )
        if not package:
            raise RuntimeError(f"Argos dil paketi bulunamadi: {source}->{target}")

        logger.info("Argos ceviri paketi indiriliyor: %s -> %s", source, target)
        path = package.download()
        argostranslate.package.install_from_path(path)
        return _installed_pair(source, target)


def _detect_language(snippets):
    text = " ".join(str(item.get("text", "")) for item in snippets)[:12000]
    if not text.strip():
        return "tr"
    try:
        detected = detect(text)
        return detected if detected in SUPPORTED else "en"
    except Exception:
        return "en"


def _translate_text(text, source):
    if source == "tr" or not text.strip():
        return text
    if source == "en":
        return _ensure_pair("en", "tr").translate(text)

    # Argos has reliable English->Turkish and common source->English pairs.
    english = _ensure_pair(source, "en").translate(text)
    return _ensure_pair("en", "tr").translate(english)


def _clean_transcript_text(text):
    text = str(text or "")
    text = text.replace("[Müzik]", " ").replace("[Music]", " ")
    text = text.replace("[Alkışlar]", " ").replace("[Applause]", " ")
    text = text.replace(">>", " ")
    return " ".join(text.split())


def translate_transcript(snippets):
    """Return Turkish snippets and the detected source language."""
    source = _detect_language(snippets)
    if source == "tr":
        return snippets, source

    translated = []
    block = []
    block_chars = 0

    def flush():
        if not block:
            return
        text = " ".join(item["text"] for item in block).strip()
        try:
            translated.append({
                "text": _translate_text(text, source),
                "start": block[0].get("start", 0),
            })
        except Exception:
            logger.exception("Argos translation failed for language %s", source)
            translated.append({"text": text, "start": block[0].get("start", 0)})
        block.clear()

    for snippet in snippets:
        text = _clean_transcript_text(snippet.get("text", ""))
        if not text:
            continue
        if block and block_chars + len(text) > 1200:
            flush()
            block_chars = 0
        block.append({"text": text, "start": snippet.get("start", 0)})
        block_chars += len(text)
    flush()
    return translated, source
