import logging
import yt_dlp
from transkriptor_pro.services.youtube_service import format_duration

logger = logging.getLogger(__name__)

def discover_videos_by_query(query, max_results=10):
    """
    Searches YouTube for videos matching the query using yt-dlp flat extraction.
    Returns a list of video dicts containing video_id, title, channel, duration, thumbnail_url.
    """
    logger.info(f"Searching YouTube for query: '{query}' (max_results={max_results})")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'skip_download': True,
    }
    
    search_query = f"ytsearch{max_results}:{query}"
    videos = []
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)
            if 'entries' in info:
                for entry in info['entries']:
                    if not entry:
                        continue
                    video_id = entry.get('id')
                    if not video_id:
                        continue
                    duration_sec = entry.get('duration')
                    videos.append({
                        'video_id': video_id,
                        'title': entry.get('title') or f"YouTube Video ({video_id})",
                        'channel': entry.get('uploader') or entry.get('channel') or 'YouTube',
                        'duration': format_duration(duration_sec),
                        'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                    })
    except Exception as e:
        logger.error(f"yt-dlp search query failed for '{query}': {e}")
        
    return videos

def discover_videos_by_channel(channel_url, max_results=10):
    """
    Crawls a YouTube channel URL to find recent videos using yt-dlp flat extraction.
    Returns a list of video dicts containing video_id, title, channel, duration, thumbnail_url.
    """
    logger.info(f"Crawling YouTube channel: '{channel_url}' (max_results={max_results})")
    
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': True,
        'skip_download': True,
        'playlistend': max_results
    }
    
    videos = []
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(channel_url, download=False)
            
            # Channel pages are extracted as playlists
            entries = info.get('entries', [])
            for entry in entries:
                if not entry:
                    continue
                video_id = entry.get('id')
                if not video_id:
                    continue
                duration_sec = entry.get('duration')
                videos.append({
                    'video_id': video_id,
                    'title': entry.get('title') or f"YouTube Video ({video_id})",
                    'channel': entry.get('uploader') or info.get('title') or 'YouTube',
                    'duration': format_duration(duration_sec),
                    'thumbnail_url': f"https://img.youtube.com/vi/{video_id}/hqdefault.jpg"
                })
    except Exception as e:
        logger.error(f"yt-dlp channel crawl failed for '{channel_url}': {e}")
        
    return videos
