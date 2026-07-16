import sqlite3
import json
from transkriptor_pro.config import Config

def get_db_connection():
    conn = sqlite3.connect(Config.DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Create videos table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS videos (
        video_id TEXT PRIMARY KEY,
        title TEXT,
        channel TEXT,
        thumbnail_url TEXT,
        duration TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """)
    
    # Create transcripts table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transcripts (
        video_id TEXT PRIMARY KEY,
        raw_transcript TEXT,
        source TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (video_id) REFERENCES videos(video_id)
    )
    """)
    
    # Create summaries table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS summaries (
        video_id TEXT PRIMARY KEY,
        short_summary TEXT,
        detailed_summary TEXT,
        summary_type TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (video_id) REFERENCES videos(video_id)
    )
    """)
    
    conn.commit()
    conn.close()

def get_cached_video(video_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM videos WHERE video_id = ?", (video_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def save_cached_video(video_id, title, channel, thumbnail_url, duration):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO videos (video_id, title, channel, thumbnail_url, duration) VALUES (?, ?, ?, ?, ?)",
            (video_id, title, channel, thumbnail_url, duration)
        )
        conn.commit()
    finally:
        conn.close()

def get_cached_transcript(video_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM transcripts WHERE video_id = ?", (video_id,)).fetchone()
    conn.close()
    if row:
        return {
            'video_id': row['video_id'],
            'raw_transcript': json.loads(row['raw_transcript']),
            'source': row['source'],
            'created_at': row['created_at']
        }
    return None

def save_cached_transcript(video_id, raw_transcript, source):
    conn = get_db_connection()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO transcripts (video_id, raw_transcript, source) VALUES (?, ?, ?)",
            (video_id, json.dumps(raw_transcript, ensure_ascii=False), source)
        )
        conn.commit()
    finally:
        conn.close()

def get_cached_summary(video_id):
    conn = get_db_connection()
    row = conn.execute("SELECT * FROM summaries WHERE video_id = ?", (video_id,)).fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def get_all_records():
    """Kayıt defteri için tüm videoları özet durumlarıyla birlikte döndürür (en yeni önce)."""
    conn = get_db_connection()
    rows = conn.execute("""
        SELECT v.video_id, v.title, v.channel, v.duration, v.created_at,
               t.source AS transcript_source,
               s.summary_type,
               CASE WHEN s.detailed_summary IS NOT NULL AND s.detailed_summary != '' THEN 1 ELSE 0 END AS has_detailed
        FROM videos v
        LEFT JOIN transcripts t ON t.video_id = v.video_id
        LEFT JOIN summaries s ON s.video_id = v.video_id
        ORDER BY v.created_at DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def save_cached_summary(video_id, short_summary, detailed_summary, summary_type):
    conn = get_db_connection()
    try:
        # Check if row exists to preserve existing values if only updating one part
        existing = conn.execute("SELECT * FROM summaries WHERE video_id = ?", (video_id,)).fetchone()
        if existing:
            # Update only non-None values or replace all if we have everything
            s_sum = short_summary if short_summary is not None else existing['short_summary']
            d_sum = detailed_summary if detailed_summary is not None else existing['detailed_summary']
            s_type = summary_type if summary_type is not None else existing['summary_type']
            
            conn.execute(
                "UPDATE summaries SET short_summary = ?, detailed_summary = ?, summary_type = ? WHERE video_id = ?",
                (s_sum, d_sum, s_type, video_id)
            )
        else:
            conn.execute(
                "INSERT INTO summaries (video_id, short_summary, detailed_summary, summary_type) VALUES (?, ?, ?, ?)",
                (video_id, short_summary, detailed_summary, summary_type)
            )
        conn.commit()
    finally:
        conn.close()
