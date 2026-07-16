import unittest
from unittest.mock import patch

from flask import Flask

from transkriptor_pro.routes.main import main_bp
from transkriptor_pro.services import colab_ai_service
from transkriptor_pro.services import youtube_service


class TranscriptRetryTests(unittest.TestCase):
    @patch.object(youtube_service.time, "sleep")
    @patch.object(
        youtube_service,
        "_fetch_transcript_once",
        side_effect=RuntimeError("blocked"),
    )
    def test_transcript_stops_after_three_attempts(self, fetch_once, sleep):
        message, success = youtube_service.fetch_transcript("abcdefghijk", 99)

        self.assertFalse(success)
        self.assertIn("3 denemede", message)
        self.assertEqual(fetch_once.call_count, 3)
        self.assertEqual(sleep.call_count, 2)


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder="../templates")
        self.app.register_blueprint(main_bp)
        self.client = self.app.test_client()

    def test_manual_transcript_endpoint_is_disabled(self):
        response = self.client.post("/api/save_manual_transcript", json={})
        self.assertEqual(response.status_code, 410)
        self.assertFalse(response.get_json()["success"])

    @patch("transkriptor_pro.routes.main.db.get_cached_summary", return_value=None)
    @patch("transkriptor_pro.routes.main.db.get_cached_transcript", return_value=None)
    @patch("transkriptor_pro.routes.main.db.get_cached_video", return_value=None)
    @patch(
        "transkriptor_pro.routes.main.yt.get_video_info",
        return_value={
            "video_id": "abcdefghijk",
            "title": "Test",
            "channel": "Test Channel",
            "duration": "1:00",
            "thumbnail_url": "",
        },
    )
    @patch(
        "transkriptor_pro.routes.main.yt.fetch_transcript",
        return_value=("failed", False),
    )
    def test_unavailable_transcript_is_skipped_without_manual_form(
        self,
        fetch_transcript,
        get_video_info,
        get_cached_video,
        get_cached_transcript,
        get_cached_summary,
    ):
        response = self.client.post("/api/transcribe", json={"url": "abcdefghijk"})
        payload = response.get_json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["error_type"], "transcript_unavailable")
        self.assertIn("3 kez", payload["error"])
        self.assertNotIn("manuel", payload["error"].lower())
        fetch_transcript.assert_called_once_with("abcdefghijk", max_attempts=3)


class ColabFormattingTests(unittest.TestCase):
    def test_transcript_sent_with_timestamps(self):
        text = colab_ai_service._format_transcript([
            {"text": "Birinci", "start": 5.2},
            {"text": "Ikinci", "start": 3661},
        ])
        self.assertEqual(text, "[00:05] Birinci\n[01:01:01] Ikinci")


if __name__ == "__main__":
    unittest.main()
