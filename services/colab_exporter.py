import os
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Default export path in project root
DEFAULT_EXPORT_DIR = Path(__file__).resolve().parent.parent / "exports"

def get_export_dir():
    """Returns the export directory path, creating it if it doesn't exist."""
    export_dir = DEFAULT_EXPORT_DIR
    if not export_dir.exists():
        export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir

def export_video_data(video_meta, raw_transcript, short_summary=None, detailed_summary=None):
    """
    Exports video metadata, transcript, and summaries to a JSON and a TXT file
    in the exports directory for portable local use.
    """
    try:
        export_dir = get_export_dir()
        video_id = video_meta['video_id']
        
        # Clean title for filename compatibility
        clean_title = "".join([c if c.isalnum() or c in "._- " else "_" for c in video_meta['title']])
        clean_title = clean_title[:50].strip() # Limit filename length
        
        # 1. JSON Export (Structured Data)
        json_data = {
            'video_id': video_id,
            'title': video_meta['title'],
            'channel': video_meta['channel'],
            'duration': video_meta.get('duration', 'Bilinmiyor'),
            'thumbnail_url': video_meta.get('thumbnail_url', ''),
            'short_summary': short_summary,
            'detailed_summary': detailed_summary,
            'transcript': raw_transcript # List of {'text', 'start', 'duration'}
        }
        
        json_filename = f"{video_id}_{clean_title}.json"
        json_path = export_dir / json_filename
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(json_data, f, ensure_ascii=False, indent=2)
            
        # 2. TXT Export (Plain text for easy AI parsing)
        txt_filename = f"{video_id}_{clean_title}.txt"
        txt_path = export_dir / txt_filename
        
        full_text = " ".join([snippet.get('text', '') for snippet in raw_transcript])
        
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(f"TITLE: {video_meta['title']}\n")
            f.write(f"CHANNEL: {video_meta['channel']}\n")
            f.write(f"VIDEO ID: {video_id}\n")
            f.write(f"DURATION: {video_meta.get('duration', 'Bilinmiyor')}\n")
            f.write("="*50 + "\n\n")
            if short_summary:
                f.write("--- SHORT SUMMARY ---\n")
                f.write(short_summary + "\n\n")
            if detailed_summary:
                f.write("--- DETAILED SUMMARY ---\n")
                f.write(detailed_summary + "\n\n")
            f.write("--- FULL TRANSCRIPT ---\n")
            f.write(full_text + "\n")
            
        logger.info(f"Successfully exported video {video_id} to {export_dir}")
        return {
            'success': True,
            'json_path': str(json_path),
            'txt_path': str(txt_path),
            'filename': json_filename
        }
    except Exception as e:
        logger.error(f"Failed to export video data: {e}")
        return {
            'success': False,
            'error': str(e)
        }

def get_all_exports():
    """Lists all exported files with metadata."""
    export_dir = get_export_dir()
    exports_list = []
    
    for file_path in export_dir.glob("*.json"):
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                exports_list.append({
                    'video_id': data.get('video_id'),
                    'title': data.get('title'),
                    'channel': data.get('channel'),
                    'duration': data.get('duration'),
                    'filename': file_path.name,
                    'txt_filename': file_path.name.replace(".json", ".txt"),
                    'created_at': os.path.getctime(file_path)
                })
        except Exception:
            continue
            
    # Sort by created time descending
    exports_list.sort(key=lambda x: x['created_at'], reverse=True)
    return exports_list
