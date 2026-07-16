import base64
import logging
from flask import Blueprint, render_template, request, jsonify
from transkriptor_pro.config import Config
import transkriptor_pro.database as db
import transkriptor_pro.services.youtube_service as yt
import transkriptor_pro.services.ocr_service as ocr
import transkriptor_pro.services.records_service as records
import transkriptor_pro.services.discovery_service as discovery
import transkriptor_pro.services.colab_exporter as exporter

main_bp = Blueprint("main", __name__)
logger = logging.getLogger(__name__)

@main_bp.route("/")
def index():
    return render_template("index.html")


def _store_transcript(video_meta, transcript_data):
    """Persist the original YouTube transcript without AI or translation."""
    db.save_cached_transcript(
        video_meta["video_id"],
        transcript_data,
        "youtube-original",
    )
    records.save_video_record(video_meta, transcript_data, None, "transcript-only")

@main_bp.route("/api/transcribe", methods=["POST"])
def transcribe():
    try:
        data = request.get_json() or {}
        url = data.get("url", "").strip()
        
        if not url:
            return jsonify({
                "success": False,
                "error": "Lütfen geçerli bir YouTube video bağlantısı veya ID'si girin."
            }), 400
            
        video_id = yt.extract_video_id(url)
        if not video_id:
            return jsonify({
                "success": False,
                "error": "Girilen bağlantıdan YouTube Video ID'si tespit edilemedi. Lütfen bağlantıyı kontrol edin."
            }), 400
            
        # 1. Check database cache.
        cached_video = db.get_cached_video(video_id)
        cached_transcript = db.get_cached_transcript(video_id)
        if cached_video and cached_transcript:
            transcript_data = cached_transcript["raw_transcript"]
            # Older records may contain translated captions. Refresh them so
            # copy-all always returns the original YouTube transcript.
            if cached_transcript.get("source") == "argos-translated":
                refreshed_transcript, refreshed = yt.fetch_transcript(
                    video_id,
                    max_attempts=3,
                )
                if refreshed:
                    transcript_data = refreshed_transcript
                    _store_transcript(cached_video, transcript_data)

            return jsonify({
                "success": True,
                "source": "cache",
                "video": cached_video,
                "transcript": transcript_data,
            })
            
        # 2. Cache miss, fetch metadata
        logger.info(f"Cache miss. Fetching details for video: {video_id}")
        video_meta = yt.get_video_info(video_id)
        
        # 3. Fetch transcript. The service performs exactly three attempts.
        transcript_data, success = yt.fetch_transcript(video_id, max_attempts=3)
        
        if not success:
            return jsonify({
                "success": False,
                "error_type": "transcript_unavailable",
                "error": "Altyazi 3 kez denendi ancak alinamadi. Bu video atlandi.",
                "details": transcript_data,
                "video": video_meta,
            }), 200

        # 4. Cache metadata and the original transcript.
        db.save_cached_video(
            video_meta["video_id"],
            video_meta["title"],
            video_meta["channel"],
            video_meta["thumbnail_url"],
            video_meta["duration"]
        )
        _store_transcript(video_meta, transcript_data)

        return jsonify({
            "success": True,
            "source": "network",
            "video": video_meta,
            "transcript": transcript_data,
        })
        
    except Exception as e:
        logger.exception("Error during transcription endpoint")
        return jsonify({
            "success": False,
            "error": "Video transkripti hazırlanırken beklenmedik bir hata oluştu. İnternet bağlantınızı kontrol edip lütfen tekrar deneyin."
        }), 500

@main_bp.route("/api/save_manual_transcript", methods=["POST"])
def save_manual_transcript():
    return jsonify({
        "success": False,
        "error": "Manuel altyazi girisi devre disi.",
    }), 410

@main_bp.route("/api/detailed_summary", methods=["POST"])
def detailed_summary():
    return jsonify({
        "success": False,
        "error": "Özetleme devre dışı. Bu uygulama yalnızca tam transkript çıkarır.",
    }), 410

@main_bp.route("/api/ocr", methods=["POST"])
def ocr_endpoint():
    try:
        data = request.get_json() or {}
        image_data = data.get("image", "").strip()
        
        if not image_data:
            return jsonify({
                "success": False,
                "error": "Lütfen analiz edilecek bir görsel yükleyin."
            }), 400
            
        # Parse base64
        # Format: data:image/png;base64,iVBORw0KGgo...
        if "," in image_data:
            header, base64_str = image_data.split(",", 1)
            mime_type = "image/png"
            if "image/jpeg" in header:
                mime_type = "image/jpeg"
            elif "image/webp" in header:
                mime_type = "image/webp"
        else:
            base64_str = image_data
            mime_type = "image/png"
            
        # Call OCR processing
        videos = ocr.process_screenshot(base64_str, mime_type)
        
        return jsonify({
            "success": True,
            "videos": videos
        })
        
    except Exception as e:
        logger.exception("Error in ocr endpoint")
        # Ensure friendly Turkish message
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500

@main_bp.route("/api/search", methods=["POST"])
def search():
    try:
        data = request.get_json() or {}
        title = data.get("title", "").strip()
        channel = data.get("channel", "").strip()
        
        if not title:
            return jsonify({
                "success": False,
                "error": "Aranacak video başlığı belirtilmedi."
            }), 400
            
        query = f"{title} {channel}".strip()
        video_meta = yt.search_video_on_youtube(
            query,
            expected_title=title,
            expected_channel=channel,
        )
        
        if not video_meta:
            return jsonify({
                "success": False,
                "error": f"YouTube üzerinde '{query}' araması için sonuç bulunamadı."
            }), 404
            
        return jsonify({
            "success": True,
            "video": video_meta
        })
        
    except Exception as e:
        logger.exception("Error in search endpoint")
        return jsonify({
            "success": False,
            "error": "Video aranırken YouTube API hatası oluştu."
        }), 500

@main_bp.route("/api/discover", methods=["POST"])
def discover():
    try:
        data = request.get_json() or {}
        query = data.get("query", "").strip()
        channel_url = data.get("channel_url", "").strip()
        max_results = int(data.get("max_results", 10))
        
        if not query and not channel_url:
            return jsonify({
                "success": False,
                "error": "Lütfen arama terimi veya kanal adresi girin."
            }), 400
            
        if channel_url:
            videos = discovery.discover_videos_by_channel(channel_url, max_results)
        else:
            videos = discovery.discover_videos_by_query(query, max_results)
            
        return jsonify({
            "success": True,
            "videos": videos
        })
    except Exception as e:
        logger.exception("Error in discover endpoint")
        return jsonify({
            "success": False,
            "error": "Videolar taranırken bir hata oluştu: " + str(e)
        }), 500

@main_bp.route("/api/export", methods=["POST"])
def export_video():
    try:
        data = request.get_json() or {}
        video_id = data.get("video_id", "").strip()
        
        if not video_id:
            return jsonify({
                "success": False,
                "error": "Geçersiz video ID."
            }), 400
            
        # 1. Ensure video metadata and transcript are cached.
        video_meta = db.get_cached_video(video_id)
        cached_transcript = db.get_cached_transcript(video_id)
        if not video_meta or not cached_transcript:
            logger.info(f"Video {video_id} not cached. Fetching and transcribing for export...")
            video_meta = yt.get_video_info(video_id)
            transcript_data, success = yt.fetch_transcript(video_id, max_attempts=3)
            if not success:
                return jsonify({
                    "success": False,
                    "error": "Altyazi 3 kez denendi ancak alinamadi. Bu video atlandi.",
                }), 400

            db.save_cached_video(video_id, video_meta['title'], video_meta['channel'], video_meta.get('thumbnail_url', ''), video_meta.get('duration', ''))
            db.save_cached_transcript(video_id, transcript_data, "youtube-original")
            cached_transcript = {'raw_transcript': transcript_data}

        # 2. Write a portable transcript export without a summary.
        export_result = exporter.export_video_data(
            video_meta,
            cached_transcript['raw_transcript'],
            None,
            None,
        )
        
        return jsonify(export_result)
        
    except Exception as e:
        logger.exception("Error in export endpoint")
        return jsonify({
            "success": False,
            "error": "İhraç işlemi sırasında bir hata oluştu: " + str(e)
        }), 500

@main_bp.route("/api/exports_list", methods=["GET"])
def exports_list():
    try:
        list_data = exporter.get_all_exports()
        return jsonify({
            "success": True,
            "exports": list_data
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500
