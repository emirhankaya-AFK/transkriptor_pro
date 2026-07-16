import base64
import io
import logging
import re

import requests
from PIL import Image
from transkriptor_pro.config import Config

logger = logging.getLogger(__name__)

def ocr_with_ocr_space(image_base64, mime_type="image/png"):
    """
    Sends the image to OCR.space API and returns the parsed text.
    image_base64: Raw base64 string (without data:image/... prefix)
    """
    api_key = Config.OCR_SPACE_KEY
    if not api_key:
        raise ValueError("OCR.space API key is not configured.")
        
    url = "https://api.ocr.space/parse/image"
    
    # OCR.space expects the base64 string to start with the data URI prefix
    # e.g., data:image/png;base64,iVBORw0KGgoAAAANSU...
    base64_data = f"data:{mime_type};base64,{image_base64}"
    
    payload = {
        "apikey": api_key,
        "base64Image": base64_data,
        "language": "tur", # Prioritize Turkish OCR
        "isOverlayRequired": True,
        "OCREngine": 2,
        "scale": True,
    }
    
    try:
        response = requests.post(url, data=payload, timeout=Config.OCR_SPACE_TIMEOUT)
        response.raise_for_status()
        res_json = response.json()
        
        if res_json.get("IsErroredOnProcessing"):
            error_msg = res_json.get("ErrorMessage") or "Unknown OCR.space processing error"
            raise Exception(f"OCR.space error: {error_msg}")
            
        parsed_results = res_json.get("ParsedResults", [])
        if not parsed_results:
            return ""
            
        parsed = parsed_results[0]
        overlay = parsed.get("TextOverlay", {}).get("Lines", [])
        lines = []
        for line in overlay:
            line_text = str(line.get("LineText", "")).strip()
            if not line_text:
                continue
            first_word = (line.get("Words") or [{}])[0]
            lines.append({
                "text": line_text,
                "top": float(first_word.get("Top", 0) or 0),
                "left": float(first_word.get("Left", 0) or 0),
            })

        return {
            "text": parsed.get("ParsedText", ""),
            "lines": lines,
        }
        
    except requests.exceptions.RequestException as e:
        logger.error(f"OCR.space request failed: {e}")
        raise Exception("OCR.space API call failed. Please check connection and API key.")

def _split_metadata_line(line, views_pattern):
    """Return a channel prefix when OCR merged channel and view metadata."""
    parts = re.split(r'\s*[·•|]\s*', line)
    if len(parts) >= 2 and any(views_pattern.search(part) for part in parts[1:]):
        return parts[0].strip()
    return None


def _parse_overlay_rows(ocr_lines, views_pattern, duration_pattern, ui_pattern):
    """Build video candidates from OCR coordinates instead of raw line order."""
    if not ocr_lines:
        return []

    ordered = sorted(
        [item for item in ocr_lines if item.get("text")],
        key=lambda item: (item.get("top", 0), item.get("left", 0)),
    )
    groups = []
    current = []
    last_top = None
    for item in ordered:
        top = float(item.get("top", 0) or 0)
        if current and last_top is not None and top - last_top > 52:
            groups.append(current)
            current = []
        current.append(item)
        last_top = top
    if current:
        groups.append(current)

    candidates = []
    for group in groups:
        # Thumbnail text can be mistaken for the real title. Keep the
        # rightmost text cluster where title/channel/metadata are displayed.
        by_left = sorted(group, key=lambda item: item.get("left", 0))
        left_values = [float(item.get("left", 0) or 0) for item in by_left]
        if len(left_values) >= 2:
            gaps = [
                (left_values[index + 1] - left_values[index], index)
                for index in range(len(left_values) - 1)
            ]
            largest_gap, gap_index = max(gaps, key=lambda item: item[0])
            if largest_gap >= 45:
                group = by_left[gap_index + 1:]

        lines = [str(item["text"]).strip() for item in group if str(item["text"]).strip()]
        if not lines:
            continue

        metadata_index = None
        channel = None
        for index, line in enumerate(lines):
            merged_channel = _split_metadata_line(line, views_pattern)
            if merged_channel:
                channel = merged_channel
                metadata_index = index
                break
            if views_pattern.search(line):
                metadata_index = index
                if index > 0:
                    channel = lines[index - 1]
                break

        title_lines = []
        if metadata_index is not None:
            before_metadata = lines[:metadata_index]
            title_lines = [
                line for line in before_metadata
                if not duration_pattern.match(line) and not ui_pattern.match(line)
            ]
            if channel in title_lines:
                title_lines.remove(channel)
        else:
            useful = [
                line for line in lines
                if len(line) >= 12
                and not duration_pattern.match(line)
                and not ui_pattern.match(line)
            ]
            if useful:
                title_lines = useful[:-1] if len(useful) > 1 and len(useful[-1]) < 55 else useful
                if not channel and len(useful) > 1 and len(useful[-1]) < 55:
                    channel = useful[-1]

        title = " ".join(title_lines).strip(" -|•")
        if len(title) < 12:
            continue
        candidates.append({
            "title": title,
            "channel": channel or "Bilinmeyen Kanal",
        })

    return candidates


def heuristic_parse_youtube_text(raw_text, ocr_lines=None):
    """
    Heuristically extracts video titles and channels from raw OCR text
    when OCR text is available but row boundaries are unclear.
    """
    if ocr_lines:
        lines = [item["text"].strip() for item in ocr_lines if item.get("text")]
    else:
        lines = [line.strip() for line in raw_text.split("\n") if line.strip()]
    videos = []
    
    # Clean patterns to identify YouTube metadata lines
    views_pattern = re.compile(
        r'\b(izlenme|görüntüleme|views?|vues?|aufrufe|visualizaciones|visualizzazioni|'
        r'önce|ago|streamed|yıl|ay|hafta|gün|saat|dakika|min(?:ute)?s?|'
        r'hours?|days?|weeks?|months?|years?|heures?|jours?|stunden|tagen?)\b',
        re.IGNORECASE,
    )
    duration_pattern = re.compile(r'^\d{1,2}:\d{2}(:\d{2})?$')
    ui_pattern = re.compile(
        r'^(shorts|ana sayfa|abonelikler|kütüphane|home|subscriptions|library|explore)$',
        re.IGNORECASE,
    )

    overlay_candidates = _parse_overlay_rows(
        ocr_lines,
        views_pattern,
        duration_pattern,
        ui_pattern,
    )
    def add_video(title, channel="Bilinmeyen Kanal"):
        title = re.sub(r'\s+', ' ', title).strip(" -|•")
        channel = re.sub(r'\s+', ' ', channel).strip(" -|•")
        if len(title) < 12 or duration_pattern.match(title) or ui_pattern.match(title):
            return
        normalized = re.sub(r'[^a-z0-9ğüşöçıİĞÜŞÖÇ]+', '', title.lower())
        if any(item["_key"] == normalized for item in videos):
            return
        videos.append({"title": title, "channel": channel, "_key": normalized})

    # Use coordinate rows first, then let the line parser fill any missing
    # cards that OCR could not group spatially.
    for candidate in overlay_candidates:
        add_video(candidate["title"], candidate.get("channel", "Bilinmeyen Kanal"))
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Check if this line looks like views/upload date info
        # e.g. "42 B izlenme • 3 gün önce" or "241K views • 1 year ago"
        if views_pattern.search(line):
            channel = None
            title = None
            
            # The line right before views/time is usually the channel name
            if i - 1 >= 0:
                channel_candidate = lines[i - 1]
                # Make sure it's not a duration or UI word
                if not duration_pattern.match(channel_candidate) and len(channel_candidate) < 60:
                    channel = channel_candidate
                    
            # The lines before the channel name are usually the video title
            if channel and i - 2 >= 0:
                title_parts = []
                idx = i - 2
                
                # Walk backward to collect the title (YouTube titles are max 2-3 lines in UI)
                while idx >= 0:
                    prev_line = lines[idx]
                    
                    # Stop if we hit a duration, UI elements, or another metadata line
                    if (duration_pattern.match(prev_line) or 
                        views_pattern.search(prev_line) or 
                        prev_line in ("Shorts", "Ana Sayfa", "Abonelikler", "Kütüphane") or
                        len(prev_line) > 120):
                        break
                        
                    title_parts.insert(0, prev_line)
                    idx -= 1
                    
                    # Limit title to last 2 collected lines
                    if len(title_parts) >= 2:
                        break
                        
                if title_parts:
                    title = " ".join(title_parts)
                    
            if title and channel:
                add_video(title, channel)
                
        i += 1
        
    # Some YouTube screenshots omit views/date text. In that case use long,
    # title-like lines and the following short line as the channel name.
    if len(videos) < 6:
        for index, line in enumerate(lines):
            if len(videos) >= 6:
                break
            if (
                len(line) < 18
                or len(line) > 140
                or duration_pattern.match(line)
                or views_pattern.search(line)
                or ui_pattern.match(line)
            ):
                continue
            if re.fullmatch(r'[\d\s.,KMBkmb]+', line):
                continue

            channel = "Bilinmeyen Kanal"
            if index + 1 < len(lines):
                possible_channel = lines[index + 1]
                if (
                    2 <= len(possible_channel) <= 60
                    and not duration_pattern.match(possible_channel)
                    and not views_pattern.search(possible_channel)
                    and not ui_pattern.match(possible_channel)
                ):
                    channel = possible_channel
            add_video(line, channel)

    # Internal deduplication metadata is never sent to the browser.
    return [
        {key: value for key, value in video.items() if key != "_key"}
        for video in videos[:6]
    ]

def parse_ocr_text(raw_text, ocr_lines=None):
    """Extract video rows locally from OCR text without an AI/API call."""
    return heuristic_parse_youtube_text(raw_text, ocr_lines)


def _encode_png(image):
    buffer = io.BytesIO()
    image.save(buffer, format="PNG", optimize=True)
    return base64.b64encode(buffer.getvalue()).decode("ascii")


def _parse_row_result(ocr_result):
    """Extract one card from a crop, keeping the right-side text cluster."""
    raw_text = ocr_result.get("text", "")
    lines = ocr_result.get("lines", [])
    candidates = parse_ocr_text(raw_text, lines)
    if not candidates:
        return None

    # A crop should contain one card. Prefer the longest useful title because
    # OCR may split the title into two candidates around the metadata line.
    return max(candidates, key=lambda item: len(item.get("title", "")))


def _process_row_crops(image_base64, mime_type="image/png", row_count=6):
    """OCR each visible feed row separately to suppress thumbnail text noise."""
    try:
        image_bytes = base64.b64decode(image_base64)
        image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as exc:
        logger.warning("Could not decode screenshot for row OCR: %s", exc)
        return []

    width, height = image.size
    if height < 360 or width < 300:
        return []

    results = []
    row_height = height / row_count
    for index in range(row_count):
        # A small overlap protects titles that sit on the boundary of two
        # bands, while keeping neighboring cards out of the crop.
        y0 = max(0, int(index * row_height - min(16, row_height * 0.08)))
        y1 = min(height, int((index + 1) * row_height + min(16, row_height * 0.08)))
        # Estimate the thumbnail's right edge from the row height and YouTube's
        # 16:9 thumbnail ratio. This adapts to narrow and wide screenshots.
        thumbnail_height = row_height * 0.85
        text_left = int((width * 0.03) + (thumbnail_height * 16 / 9) + (width * 0.01))
        text_left = max(int(width * 0.30), min(text_left, int(width * 0.39)))
        crop = image.crop((text_left, y0, width, y1))
        try:
            crop_result = ocr_with_ocr_space(_encode_png(crop), "image/png")
            candidate = _parse_row_result(crop_result)
            if candidate:
                results.append(candidate)
        except Exception as exc:
            logger.warning("Row OCR failed for row %s: %s", index + 1, exc)

    return results


def _merge_video_candidates(primary, fallback):
    merged = []
    seen = set()
    for candidate in list(primary) + list(fallback):
        title = re.sub(r"[^a-z0-9ğüşöçıİĞÜŞÖÇ]+", "", candidate.get("title", "").lower())
        if len(title) < 12 or title in seen:
            continue
        seen.add(title)
        merged.append({
            "title": candidate.get("title", "").strip(),
            "channel": candidate.get("channel", "Bilinmeyen Kanal").strip(),
        })
    return merged[:6]

def process_screenshot(image_base64, mime_type="image/png"):
    """
    Main function to process screenshot.
    OCR.space reads the screenshot; local rules extract video rows.
    """
    errors = []
    
    logger.info("Using OCR.space and local video extraction...")
    try:
        ocr_result = ocr_with_ocr_space(image_base64, mime_type)
        raw_text = ocr_result.get("text", "")
        if not raw_text.strip():
            raise Exception("OCR.space parsed the image but returned no text.")
            
        logger.info("OCR.space extracted text successfully. Structuring...")
        full_image_videos = parse_ocr_text(raw_text, ocr_result.get("lines", []))

        # The full screenshot is useful for recovery, but row OCR is the
        # authoritative path for feed screenshots: thumbnail captions often
        # look like video titles to a single whole-image OCR pass.
        row_videos = _process_row_crops(image_base64, mime_type, row_count=6)
        videos = _merge_video_candidates(row_videos, full_image_videos)
        if videos:
            return videos
            
    except Exception as e:
        err_msg = f"OCR.space fallback failed: {e}"
        logger.error(err_msg)
        errors.append(err_msg)
        
    # If everything failed, raise an informative Turkish exception
    if not Config.OCR_SPACE_KEY:
        raise Exception(
            "Görsel analizi yapılamadı. OCR.space API anahtarı eksik. "
            "Lütfen .env dosyasını yapılandırın."
        )
        
    raise Exception(
        f"Görsel analizi sırasında hata oluştu. Hata detayları:\n" + "\n".join(errors)
    )
