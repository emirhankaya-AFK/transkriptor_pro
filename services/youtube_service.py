import json
import re
import logging
import time
from difflib import SequenceMatcher
import requests
import yt_dlp
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled
from youtube_transcript_api.proxies import GenericProxyConfig
from transkriptor_pro.config import Config

logger = logging.getLogger(__name__)

def extract_video_id(url):
    """
    Extracts the 11-character YouTube video ID from various formats of YouTube URLs.
    """
    url = url.strip()
    
    # Common regex patterns for YouTube video IDs
    patterns = [
        r'(?:v=|\/embed\/|\/v\/|\/shorts\/|youtu\.be\/)([a-zA-Z0-9_-]{11})',
        r'(?:watch\?v=)([a-zA-Z0-9_-]{11})',
        r'^([a-zA-Z0-9_-]{11})$'  # Raw 11-char ID
    ]
    
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
            
    return None

def format_duration(seconds):
    """Formats duration in seconds to HH:MM:SS or MM:SS format."""
    if not seconds:
        return "0:00"
    try:
        seconds = int(seconds)
        h = seconds // 3600
        m = (seconds % 3600) // 60
        s = seconds % 60
        if h > 0:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
    except Exception:
        return "0:00"

def get_video_info(video_id):
    """
    Fetches video metadata (title, channel, duration, thumbnail) using yt-dlp.
    """
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'skip_download': True,
        'format': 'best'
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            duration_sec = info.get('duration')
            return {
                'video_id': video_id,
                'title': info.get('title') or f"YouTube Video ({video_id})",
                'channel': info.get('uploader') or info.get('channel') or 'YouTube',
                'duration': format_duration(duration_sec),
                'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
            }
    except Exception as e:
        logger.error(f"yt-dlp metadata extraction failed for {video_id}: {e}")
        # Fallback metadata if extraction fails
        return {
            'video_id': video_id,
            'title': f"YouTube Video ({video_id})",
            'channel': "YouTube",
            'duration': "Bilinmiyor",
            'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
        }

def _normalize_search_text(text):
    value = (text or '').casefold()
    value = value.replace('ı', 'i').replace('ğ', 'g').replace('ü', 'u')
    value = value.replace('ş', 's').replace('ö', 'o').replace('ç', 'c')
    return re.sub(r'[^a-z0-9]+', ' ', value).strip()


def _match_score(expected_title, expected_channel, actual_title, actual_channel):
    title_a = _normalize_search_text(expected_title)
    title_b = _normalize_search_text(actual_title)
    channel_a = _normalize_search_text(expected_channel)
    channel_b = _normalize_search_text(actual_channel)
    title_ratio = SequenceMatcher(None, title_a, title_b).ratio()
    expected_words = [word for word in title_a.split() if len(word) > 1]
    actual_words = [word for word in title_b.split() if len(word) > 1]
    expected_set = set(expected_words)
    actual_set = set(actual_words)
    exact_matches = expected_set & actual_set

    # OCR frequently changes one or two characters (Trump -> Trurnp). Count a
    # close word as a match, but only for meaningful words to avoid false hits.
    fuzzy_matches = 0
    unmatched_actual = actual_set - exact_matches
    for expected_word in expected_set - exact_matches:
        if len(expected_word) < 4:
            continue
        best = max(
            (SequenceMatcher(None, expected_word, actual_word).ratio()
             for actual_word in unmatched_actual),
            default=0,
        )
        if best >= 0.78:
            fuzzy_matches += 1

    matched_count = len(exact_matches) + (fuzzy_matches * 0.75)
    recall = matched_count / max(1, len(expected_set))
    precision = matched_count / max(1, len(actual_set))
    word_score = (2 * recall * precision / (recall + precision)) if recall + precision else 0
    ordered_title = ' '.join(expected_words)
    phrase_bonus = 1.0 if ordered_title and ordered_title in title_b else 0.0

    unknown_channel = channel_a in ('', 'bilinmeyen kanal', 'youtube')
    channel_ratio = 0.0 if unknown_channel else SequenceMatcher(None, channel_a, channel_b).ratio()
    title_score = (title_ratio * 0.48) + (word_score * 0.42) + (phrase_bonus * 0.10)
    if unknown_channel:
        return title_score
    return (title_score * 0.88) + (channel_ratio * 0.12)


def _video_meta_from_entry(entry):
    video_id = entry.get('id')
    if not video_id:
        return None
    return {
        'video_id': video_id,
        'title': entry.get('title') or '',
        'channel': entry.get('uploader') or entry.get('channel') or 'YouTube',
        'duration': format_duration(entry.get('duration')),
        'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg",
    }


def _search_entries(ydl, query, limit=10):
    info = ydl.extract_info(f"ytsearch{limit}:{query}", download=False)
    return [entry for entry in info.get('entries', []) if entry and entry.get('id')]


def _build_search_queries(title, channel):
    """Create resilient queries from a possibly damaged OCR title."""
    clean_title = _normalize_search_text(title)
    clean_channel = _normalize_search_text(channel)
    words = [word for word in clean_title.split() if len(word) > 2]
    # Keep the first occurrence of repeated OCR/thumbnail words. Repetition is
    # common when the thumbnail caption and title contain the same phrase.
    unique_words = list(dict.fromkeys(words))
    queries = []

    def add(value):
        value = re.sub(r'\s+', ' ', value or '').strip()
        if value and value not in queries:
            queries.append(value)

    add(f'{title} {channel}' if clean_channel not in ('', 'bilinmeyen kanal', 'youtube') else title)
    add(title)
    if len(unique_words) >= 6:
        # The first OCR word is often thumbnail text (for example "DALLAS")
        # inserted before the real title. Retry without that word early.
        add(' '.join(unique_words[1:]))
    # YouTube titles commonly use pipes to separate clauses. OCR may capture
    # only the final clause, which is often still an exact searchable phrase.
    title_parts = [
        part.strip()
        for part in re.split(r'\s*[|•]\s*', title or '')
        if len(_normalize_search_text(part).split()) >= 2
    ]
    for part in reversed(title_parts):
        add(part)
    if unique_words:
        add(' '.join(unique_words))
        add(' '.join(unique_words[:8]))
        if len(unique_words) > 8:
            add(' '.join(unique_words[-8:]))
        # Long and distinctive words survive OCR better than short UI noise.
        distinctive = sorted(
            unique_words,
            key=lambda word: (-len(word), unique_words.index(word)),
        )[:7]
        add(' '.join(distinctive))
    if clean_channel not in ('', 'bilinmeyen kanal', 'youtube'):
        add(f'{" ".join(unique_words[:7])} {channel}')
    return queries[:5]


def _detect_search_language(title):
    """Keep YouTube from auto-translating Turkish titles during search."""
    raw = (title or '').casefold()
    words = set(_normalize_search_text(title).split())
    turkish_markers = {
        'bir', 've', 'ile', 'icin', 'neden', 'nerede', 'kimsenin',
        'borsada', 'altin', 'altindaki', 'oyunlari', 'sey', 'bilen',
    }
    if re.search(r'[çğıöşü]', raw) or words & turkish_markers:
        return 'tr'
    return 'en'


def _entry_channel_url(entry):
    channel_url = entry.get('channel_url') or entry.get('uploader_url')
    if channel_url:
        return channel_url.rstrip('/') + '/videos'
    channel_id = entry.get('channel_id') or entry.get('uploader_id')
    if channel_id and str(channel_id).startswith('UC'):
        return f"https://www.youtube.com/channel/{channel_id}/videos"
    return None


def _find_channel_url(ydl, channel_name):
    """Resolve a noisy OCR channel name to a real YouTube channel URL."""
    if not channel_name or len(channel_name.strip()) < 2:
        return None
    try:
        entries = _search_entries(ydl, channel_name, limit=10)
    except Exception as exc:
        logger.warning("Channel lookup failed for %r: %s", channel_name, exc)
        return None

    ranked = sorted(
        entries,
        key=lambda entry: SequenceMatcher(
            None,
            _normalize_search_text(channel_name),
            _normalize_search_text(entry.get('uploader') or entry.get('channel') or ''),
        ).ratio(),
        reverse=True,
    )
    for entry in ranked:
        actual_channel = entry.get('uploader') or entry.get('channel') or ''
        ratio = SequenceMatcher(
            None,
            _normalize_search_text(channel_name),
            _normalize_search_text(actual_channel),
        ).ratio()
        if ratio < 0.35:
            continue
        channel_url = _entry_channel_url(entry)
        if channel_url:
            return channel_url
    return None


def _search_inside_channel(ydl, channel_url, expected_title, expected_channel):
    """Search a resolved channel's own video list, not global results."""
    try:
        info = ydl.extract_info(channel_url, download=False)
        entries = [entry for entry in info.get('entries', []) if entry and entry.get('id')]
    except Exception as exc:
        logger.warning("Channel video crawl failed for %s: %s", channel_url, exc)
        return None

    ranked = sorted(
        (
            _match_score(
                expected_title,
                expected_channel,
                entry.get('title', ''),
                entry.get('uploader') or entry.get('channel') or expected_channel,
            ),
            entry,
        )
        for entry in entries
    )
    if not ranked:
        return None
    score, entry = ranked[-1]
    if score < 0.35:
        logger.warning("No reliable match inside channel %s (score %.2f)", channel_url, score)
        return None
    return _video_meta_from_entry(entry)


def search_video_on_youtube(query, expected_title='', expected_channel=''):
    """
    Searches YouTube using yt-dlp and returns video details.
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'skip_download': True,
        'format': 'best',
        'extractor_args': {
            'youtube': {
                'lang': [_detect_search_language(expected_title or query)],
            },
        },
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            entries_by_id = {}
            queries = _build_search_queries(expected_title or query, expected_channel)
            for query_index, search_query in enumerate(queries):
                try:
                    result_limit = 10 if query_index == 0 else 7
                    for entry in _search_entries(ydl, search_query, limit=result_limit):
                        entries_by_id.setdefault(entry.get('id'), entry)
                except Exception as exc:
                    logger.warning("YouTube query failed for %r: %s", search_query, exc)

                # Stop querying as soon as the accumulated pool contains a
                # convincing match. Alternative searches are only a fallback.
                interim_ranked = sorted(
                    (
                        _match_score(
                            expected_title or query,
                            expected_channel,
                            item.get('title', ''),
                            item.get('uploader') or item.get('channel') or '',
                        ),
                        item,
                    )
                    for item in entries_by_id.values()
                )
                if interim_ranked:
                    interim_score, interim_entry = interim_ranked[-1]
                    confidence_target = 0.72 if query_index == 0 else 0.62
                    if interim_score >= confidence_target:
                        return _video_meta_from_entry(interim_entry)

                # Three materially different queries are enough. Later query
                # variants tend to add latency and unrelated results.
                if query_index >= 2:
                    break
            entries = list(entries_by_id.values())
            if entries:
                ranked = sorted(
                    [(
                        _match_score(
                            expected_title or query,
                            expected_channel,
                            item.get('title', ''),
                            item.get('uploader') or item.get('channel') or '',
                        ),
                        item,
                    ) for item in entries],
                    key=lambda pair: pair[0],
                )
                best_score, entry = ranked[-1]
                # A low score is more dangerous than a skipped video. This
                # prevents OCR fragments from opening an unrelated video.
                expected_word_count = len(_normalize_search_text(expected_title).split())
                minimum_score = 0.40 if expected_word_count >= 5 else 0.48
                if expected_title and best_score < minimum_score:
                    logger.warning(
                        "No reliable YouTube match for %r (score %.2f)",
                        expected_title,
                        best_score,
                    )
                else:
                    return _video_meta_from_entry(entry)

                # OCR may not have captured the channel name. Use the channel
                # attached to the best global results and verify the title in
                # each channel's own video feed before giving up.
                channel_entries = sorted(
                    entries,
                    key=lambda item: _match_score(
                        expected_title or query,
                        '',
                        item.get('title', ''),
                        item.get('uploader') or item.get('channel') or '',
                    ),
                    reverse=True,
                )
                checked_channels = set()
                for channel_entry in channel_entries[:3]:
                    channel_url = _entry_channel_url(channel_entry)
                    if not channel_url or channel_url in checked_channels:
                        continue
                    checked_channels.add(channel_url)
                    channel_match = _search_inside_channel(
                        ydl,
                        channel_url,
                        expected_title or query,
                        channel_entry.get('uploader') or channel_entry.get('channel') or '',
                    )
                    if channel_match:
                        return channel_match

            # Global results were not reliable enough. Resolve the channel
            # and search its own video feed before reporting a failure.
            if expected_channel:
                channel_url = _find_channel_url(ydl, expected_channel)
                if channel_url:
                    channel_match = _search_inside_channel(
                        ydl,
                        channel_url,
                        expected_title or query,
                        expected_channel,
                    )
                    if channel_match:
                        logger.info(
                            "Video found inside channel %r: %s",
                            expected_channel,
                            channel_match.get('title'),
                        )
                        return channel_match
    except Exception as e:
        logger.error(f"yt-dlp search failed for '{query}': {e}")
        
    return None

def _create_transcript_api():
    if not Config.TRANSCRIPT_PROXY_URL:
        return YouTubeTranscriptApi()

    proxy_config = GenericProxyConfig(
        http_url=Config.TRANSCRIPT_PROXY_URL,
        https_url=Config.TRANSCRIPT_PROXY_URL,
    )
    return YouTubeTranscriptApi(proxy_config=proxy_config)


def _fetch_transcript_once(video_id):
    api = _create_transcript_api()
    transcript_list = api.list(video_id)
    available = list(transcript_list)
    if not available:
        raise RuntimeError("Bu video icin kullanilabilir altyazi bulunamadi.")

    # No translation is requested here. Prefer a human-created track, then the
    # video's original/default track, and use generated captions only as fallback.
    selected = next(
        (item for item in available if not item.is_generated and item.language_code == 'tr'),
        None,
    )
    selected = selected or next((item for item in available if not item.is_generated), None)
    selected = selected or next(
        (item for item in available if item.language_code in ('tr', 'en')),
        None,
    )
    selected = selected or available[0]
    return selected.fetch().to_raw_data()


def _fetch_transcript_via_caption_proxy(video_id):
    """Fetch the original caption track when YouTube blocks timedtext locally."""
    url = f"https://www.youtube.com/watch?v={video_id}"
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    def select_track(track_groups):
        keys = [key for key in track_groups if key != 'live_chat']
        if not keys:
            return None
        original_language = info.get('language')
        preferred_keys = (
            [key for key in keys if key.endswith('-orig')]
            + ([original_language] if original_language in keys else [])
            + [key for key in ('tr', 'en') if key in keys]
            + keys
        )
        for key in preferred_keys:
            formats = track_groups.get(key) or []
            json_format = next(
                (item for item in formats if item.get('ext') == 'json3'),
                None,
            )
            if json_format and json_format.get('url'):
                return json_format['url']
        return None

    caption_url = select_track(info.get('subtitles') or {})
    caption_url = caption_url or select_track(info.get('automatic_captions') or {})
    if not caption_url:
        raise RuntimeError("Video icin indirilebilir altyazi izi bulunamadi.")

    proxied_url = "https://r.jina.ai/http://" + caption_url.split("://", 1)[-1]
    response = requests.get(proxied_url, timeout=45)
    response.raise_for_status()
    marker = "Markdown Content:"
    if marker not in response.text:
        raise RuntimeError("Altyazi gecidi beklenen JSON verisini dondurmedi.")
    payload = json.loads(response.text.split(marker, 1)[1].strip())

    transcript = []
    for event in payload.get('events', []):
        text = ''.join(
            segment.get('utf8', '')
            for segment in event.get('segs', [])
        ).replace('\n', ' ').strip()
        if not text:
            continue
        start = float(event.get('tStartMs', 0) or 0) / 1000
        duration = float(event.get('dDurationMs', 0) or 0) / 1000
        transcript.append({
            'text': text,
            'start': start,
            'duration': max(duration, 0.1),
        })
    if not transcript:
        raise RuntimeError("Altyazi gecidi bos transkript dondurdu.")
    return transcript


def fetch_transcript(video_id, max_attempts=3):
    """
    Fetches a transcript with three bounded attempts.

    A configured trusted proxy is used for the complete API flow. Public proxy
    lists and browser cookies are deliberately not used.
    """
    attempts = max(1, min(int(max_attempts), 3))
    errors = []

    for attempt in range(1, attempts + 1):
        try:
            transcript = _fetch_transcript_once(video_id)
            if transcript:
                logger.info(
                    "Transcript fetched for %s on attempt %s/%s",
                    video_id,
                    attempt,
                    attempts,
                )
                return transcript, True
            raise RuntimeError("YouTube bos bir transkript dondurdu.")
        except Exception as exc:
            errors.append(f"{type(exc).__name__}: {exc}")
            logger.warning(
                "Transcript attempt %s/%s failed for %s: %s",
                attempt,
                attempts,
                video_id,
                exc,
            )
            try:
                transcript = _fetch_transcript_via_caption_proxy(video_id)
                logger.info("Transcript fetched through caption fallback for %s", video_id)
                return transcript, True
            except Exception as fallback_exc:
                errors.append(f"CaptionFallback: {fallback_exc}")
                logger.warning(
                    "Caption fallback failed for %s: %s",
                    video_id,
                    fallback_exc,
                )
            if attempt < attempts:
                time.sleep(2 ** (attempt - 1))

    logger.error("Transcript unavailable for %s after %s attempts", video_id, attempts)
    return f"Altyazi {attempts} denemede alinamadi. Son hata: {errors[-1]}", False

def parse_time_to_seconds(time_str):
    """Parses timestamp string (HH:MM:SS or MM:SS) to float seconds."""
    parts = time_str.replace(',', '.').split(':')
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        elif len(parts) == 2:
            return int(parts[0]) * 60 + float(parts[1])
    except ValueError:
        pass
    return 0.0

def parse_manual_transcript(text):
    """
    Parses manually pasted transcripts.
    Handles SRT, WebVTT, bracketed time [MM:SS] or prefix time MM:SS.
    If no timestamps are present, assigns artificial 5-second intervals.
    """
    lines = text.strip().split('\n')
    snippets = []
    
    # Check for SRT/WebVTT arrow format: "00:01:20,000 --> 00:01:23,000"
    srt_arrow_pattern = re.compile(
        r'(\d{1,2}:\d{2}:\d{2}[,\.]\d{3}|\d{2}:\d{2}[,\.]\d{3})\s*-->\s*(\d{1,2}:\d{2}:\d{2}[,\.]\d{3}|\d{2}:\d{2}[,\.]\d{3})'
    )
    
    is_srt = False
    for line in lines[:10]:
        if srt_arrow_pattern.search(line):
            is_srt = True
            break
            
    if is_srt:
        current_start = None
        current_text = []
        
        for line in lines:
            line = line.strip()
            if not line:
                if current_start is not None and current_text:
                    snippets.append({
                        'text': " ".join(current_text),
                        'start': current_start,
                        'duration': 5.0
                    })
                    current_start = None
                    current_text = []
                continue
                
            # Skip SRT line numbers
            if line.isdigit() and current_start is None:
                continue
                
            match = srt_arrow_pattern.search(line)
            if match:
                if current_start is not None and current_text:
                    snippets.append({
                        'text': " ".join(current_text),
                        'start': current_start,
                        'duration': 5.0
                    })
                current_start = parse_time_to_seconds(match.group(1))
                current_text = []
            else:
                if current_start is not None:
                    current_text.append(line)
                    
        if current_start is not None and current_text:
            snippets.append({
                'text': " ".join(current_text),
                'start': current_start,
                'duration': 5.0
            })
            
        return snippets

    # Bracketed / Prefix patterns
    # [01:23] Hello or 01:23 Hello or 1:02:15 Hello
    bracket_pattern = re.compile(r'^\[(?:(\d{1,2}):)?(\d{1,2}):(\d{2})(?:\.(\d+))?\]\s*(.*)$')
    prefix_pattern = re.compile(r'^(?:(?:(\d{1,2}):)?(\d{1,2}):(\d{2}))(?:\s*-\s*|\s+)(.*)$')
    
    for line in lines:
        line = line.strip()
        if not line:
            continue
            
        match_b = bracket_pattern.match(line)
        match_p = prefix_pattern.match(line)
        
        if match_b:
            hh, mm, ss, ms, content = match_b.groups()
            hh = int(hh) if hh else 0
            mm = int(mm)
            ss = int(ss)
            start_sec = hh * 3600 + mm * 60 + ss
            if ms:
                start_sec += float(f"0.{ms}")
            snippets.append({
                'text': content.strip(),
                'start': start_sec,
                'duration': 5.0
            })
        elif match_p:
            hh, mm, ss, content = match_p.groups()
            hh = int(hh) if hh else 0
            mm = int(mm)
            ss = int(ss)
            start_sec = hh * 3600 + mm * 60 + ss
            snippets.append({
                'text': content.strip(),
                'start': start_sec,
                'duration': 5.0
            })
        else:
            snippets.append({
                'text': line,
                'start': None,
                'duration': 5.0
            })
            
    # If no timestamps were found, auto-generate sequential times
    has_timestamps = any(s['start'] is not None for s in snippets)
    if not has_timestamps:
        for idx, s in enumerate(snippets):
            s['start'] = float(idx * 5)
    else:
        # Fill in missing times by carrying forward
        last_time = 0.0
        for s in snippets:
            if s['start'] is None:
                s['start'] = last_time + 5.0
            last_time = s['start']
            
    # Calculate durations based on successive starts
    for idx in range(len(snippets) - 1):
        snippets[idx]['duration'] = max(0.5, snippets[idx+1]['start'] - snippets[idx]['start'])
        
    return snippets
