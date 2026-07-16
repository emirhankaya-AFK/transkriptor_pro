"""Kalıcı kayıt arşivi: işlenen her video Documents/Transkriptor_Kayitlari
klasörüne yazılır. Her video kendi klasörünü alır (transkript + özetler),
KAYIT_DEFTERI.md ise tüm geçmişin dökümünü tutar.
"""
import os
import re
import logging
from datetime import datetime

import transkriptor_pro.database as db

logger = logging.getLogger(__name__)

RECORDS_DIR = os.path.expanduser("~/Documents/Transkriptor_Kayitlari")


def _slugify(title, max_len=60):
    """Dosya sistemi için güvenli klasör adı üretir."""
    slug = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '', title or 'video').strip()
    slug = re.sub(r'\s+', ' ', slug)
    return slug[:max_len].strip() or 'video'


def _video_dir(video_id, title):
    return os.path.join(RECORDS_DIR, f"{_slugify(title)} [{video_id}]")


def _format_time(seconds):
    sec = int(seconds or 0)
    h, m, s = sec // 3600, (sec % 3600) // 60, sec % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"


def save_video_record(video_meta, transcript, short_summary, summary_type):
    """Transkript alınan videoyu diske kaydeder ve kayıt defterini günceller."""
    try:
        vdir = _video_dir(video_meta["video_id"], video_meta.get("title"))
        os.makedirs(vdir, exist_ok=True)

        now = datetime.now().strftime("%d.%m.%Y %H:%M")

        with open(os.path.join(vdir, "bilgi.txt"), "w", encoding="utf-8") as f:
            f.write(
                f"VİDEO   : {video_meta.get('title', '')}\n"
                f"KANAL   : {video_meta.get('channel', '')}\n"
                f"SÜRE    : {video_meta.get('duration', '')}\n"
                f"LİNK    : https://www.youtube.com/watch?v={video_meta['video_id']}\n"
                f"TARİH   : {now}\n"
            )

        with open(os.path.join(vdir, "transkript.txt"), "w", encoding="utf-8") as f:
            for line in transcript or []:
                f.write(f"[{_format_time(line.get('start'))}] {line.get('text', '')}\n")

        if short_summary:
            with open(os.path.join(vdir, "kisa_ozet.txt"), "w", encoding="utf-8") as f:
                f.write(f"KISA ÖZET — {video_meta.get('title', '')}\n\n{short_summary}\n")

        rebuild_index()
        logger.info(f"Kayıt diske yazıldı: {vdir}")
    except Exception:
        logger.exception("Video kaydı diske yazılamadı (uygulama akışı etkilenmez).")


def save_detailed_record(video_id, detailed_summary):
    """Detaylı özet istenen videonun klasörüne ders notunu ekler."""
    try:
        video = db.get_cached_video(video_id) or {"title": "video"}
        vdir = _video_dir(video_id, video.get("title"))
        os.makedirs(vdir, exist_ok=True)
        with open(os.path.join(vdir, "detayli_ozet.txt"), "w", encoding="utf-8") as f:
            f.write(f"DETAYLI DERS NOTU — {video.get('title', '')}\n\n{detailed_summary}\n")
        rebuild_index()
        logger.info(f"Detaylı özet kaydedildi: {vdir}")
    except Exception:
        logger.exception("Detaylı özet diske yazılamadı (uygulama akışı etkilenmez).")


def rebuild_index():
    """KAYIT_DEFTERI.md dosyasını veritabanındaki tüm kayıtlardan yeniden üretir."""
    try:
        os.makedirs(RECORDS_DIR, exist_ok=True)
        records = db.get_all_records()

        lines = [
            "# 📼 Transkriptör Kayıt Defteri",
            "",
            f"Toplam **{len(records)}** video işlendi. Her videonun klasöründe "
            "`transkript.txt`, `kisa_ozet.txt` ve (istendiyse) `detayli_ozet.txt` bulunur.",
            "",
            "| Tarih | Video | Kanal | Süre | Detaylı Özet | Link |",
            "|---|---|---|---|---|---|",
        ]
        for r in records:
            title = (r.get("title") or "?").replace("|", "¦")
            channel = (r.get("channel") or "?").replace("|", "¦")
            detailed = "✅ Alındı" if r.get("has_detailed") else "—"
            date = (r.get("created_at") or "")[:16]
            link = f"https://www.youtube.com/watch?v={r['video_id']}"
            lines.append(
                f"| {date} | {title} | {channel} | {r.get('duration') or '?'} | {detailed} | {link} |"
            )

        with open(os.path.join(RECORDS_DIR, "KAYIT_DEFTERI.md"), "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
    except Exception:
        logger.exception("Kayıt defteri güncellenemedi.")
