import logging
import sys
import os

# Add parent directory of this script to sys.path to enable absolute package imports
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from flask import Flask
from transkriptor_pro.config import Config
import transkriptor_pro.database as db
from transkriptor_pro.routes.main import main_bp

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    # Initialize SQLite database
    logger.info("Veritabanı başlatılıyor...")
    db.init_db()

    # Kayıt defterini güncelle (Documents/Transkriptor_Kayitlari)
    from transkriptor_pro.services import records_service
    records_service.rebuild_index()
    
    # Register blueprints
    app.register_blueprint(main_bp)
    
    return app

if __name__ == "__main__":
    app = create_app()
    
    # Display friendly Turkish info on startup
    print("\n" + "="*50)
    print("🚀 TRANSKRİPTÖR PRO - YOUTUBE VIDEO TRANSKRİPT & ÖZET ASİSTANI")
    print("="*50)
    print(f"📡 Sunucu adresi: http://{Config.HOST}:{Config.PORT}")
    print(f"📂 Veritabanı yolu: {Config.DATABASE_PATH}")
    print("🔒 Güvenli yerel sunucu modu aktif.")
    print("="*50 + "\n")
    
    app.run(host=Config.HOST, port=Config.PORT, debug=Config.DEBUG)
