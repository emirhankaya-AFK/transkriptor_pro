import sys
import os

# Set path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)
os.environ["PYTHONPATH"] = parent_dir + os.pathsep + os.environ.get("PYTHONPATH", "")

import transkriptor_pro.services.discovery_service as discovery
import transkriptor_pro.services.colab_exporter as exporter
import transkriptor_pro.services.youtube_service as yt

def test_discovery():
    print("Testing Video Discovery...")
    videos = discovery.discover_videos_by_query("beste uyanık", max_results=3)
    print(f"Found {len(videos)} videos:")
    for v in videos:
        print(f"- {v['title']} (ID: {v['video_id']}, Channel: {v['channel']})")
    assert len(videos) > 0, "Discovery search failed to return results!"
    print("✅ Discovery test passed!")

def test_export():
    print("\nTesting Colab Exporter...")
    video_meta = {
        'video_id': '1l6SNE-itDI',
        'title': 'TEST VIDEO',
        'channel': 'TEST CHANNEL',
        'duration': '5:00',
        'thumbnail_url': 'http://test.com/thumb.jpg'
    }
    raw_transcript = [{'text': 'Hello world', 'start': 0.0, 'duration': 2.0}]
    res = exporter.export_to_colab(video_meta, raw_transcript, "Short test", "Detailed test")
    print("Export Result:", res)
    assert res['success'] is True, "Export failed!"
    assert os.path.exists(res['json_path']), "JSON file not created!"
    assert os.path.exists(res['txt_path']), "TXT file not created!"
    
    # Clean up test export files
    os.remove(res['json_path'])
    os.remove(res['txt_path'])
    print("✅ Export test passed!")

if __name__ == "__main__":
    try:
        test_discovery()
        test_export()
        print("\n🎉 ALL TESTS PASSED SUCCESSFULLY!")
    except Exception as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
