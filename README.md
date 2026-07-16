# Transkriptör Pro — YouTube Video Transkript ve AI Özet Asistanı

Transkriptör Pro; YouTube videolarının altyazılarını çeken, otomatik Türkçe kısa özetler oluşturan ve ders notu formatında detaylı çıktılar sunan üretim kalitesinde (production-ready) bir Python & Flask web uygulamasıdır.

Ayrıca YouTube ana sayfasından veya arama sonuçlarından alınmış **ekran görüntülerini** sürükleyip bırakarak (veya Ctrl+V ile yapıştırarak) görseldeki videoları yapay zeka/OCR kullanarak otomatik tespit edebilir ve YouTube üzerinde tek tıkla aratarak analiz edebilirsiniz.

---

## Özellikler

1. **YouTube URL Desteği:** YouTube bağlantısı veya video ID girilerek saniyeler içinde altyazı ve özet çekilir.
2. **Ekran Görüntüsü Analizi (OCR/Multimodal):** Video listesi içeren bir resim yüklendiğinde, görseldeki video başlıkları ve kanal adları algılanır ve arama adayları olarak listelenir.
3. **Hata Toleranslı Gemini API Fallback Zinciri:**
   - Özetleme ve OCR istekleri sırasıyla `gemini-2.5-flash` ➔ `gemini-2.5-flash-lite` ➔ `gemini-2.0-flash` modellerini dener.
   - 503/429 durumlarında üstel bekleme (exponential backoff: 2sn, 4sn, 6sn) ile yeniden deneme (retry) yapar.
4. **Yerel Özetleyici (Yedek Mekanizma):** Gemini kotaları dolduysa veya API anahtarı yoksa, Türkçe stopword temizliği ve kelime frekans analizi içeren yerel algoritmaya düşer. Altyazıda noktalama işareti yoksa metni ~30'ar kelimelik cümlelere böler ve sarı renkli `⚠️ AI kotası dolu, basit özet gösteriliyor` uyarısıyla sonucu gösterir.
5. **OCR.space Fallback:** Gemini Multimodal başarısız olursa, OCR.space API'si üzerinden metin okunup Gemini metin modeliyle veya yerel heuristiklerle ayrıştırılır.
6. **SQLite Kalıcı Önbellek:** Analiz edilen videolar, transkriptler ve özetler SQLite veritabanına kaydedilir; aynı video tekrar istendiğinde anında veritabanından yüklenir.
7. **Premium Tasarım:** Cam efekti (glassmorphism) barındıran, responsive (mobilde tek kolon), light/dark tema geçişli modern arayüz.
8. **Zaman Damgalı Görünüm:** Altyazı satırlarının süresine tıklandığında ilgili saniyeden YouTube videosu yeni sekmede açılır.
9. **Kopyalama ve İndirme:** Transkriptler panoya kopyalanabilir veya `.txt` dosyası olarak indirilebilir.

---

## Kurulum ve Başlatma

### Gereksinimler
- Python 3.12+
- Linux (Ubuntu/Debian veya uyumlu bir dağıtım)

### 1. Kurulum Adımları
Projeyi çalıştırmak için bağımlılıkları yükleyin:

```bash
# Proje dizinine girin
cd transkriptor_pro

# Sanal ortam oluşturun ve aktif edin
python3 -m venv venv
source venv/bin/activate

# Gerekli kütüphaneleri yükleyin
pip install -r requirements.txt
```

### 2. API Anahtarları (.env Yapılandırması)
Proje kök dizininde `.env` dosyasını oluşturun veya mevcut `.env` dosyasını düzenleyin:

```env
# Gemini API Key (Zorunludur)
GEMINI_API_KEY=KENDI_GEMINI_API_ANAHTARINIZ

# OCR.space API Key (İsteğe bağlı, varsayılan olarak helloworld kuruludur)
OCR_SPACE_KEY=helloworld
```

### 3. Uygulamayı Çalıştırma
#### Manuel Çalıştırma:
```bash
python3 app.py
```
Uygulama çalıştıktan sonra tarayıcınızdan **`http://127.0.0.1:5000`** adresine gidin.

#### Kolay Linux Scripti ile Çalıştırma:
Gelişmiş başlatıcı betik port kontrolü yapar, meşgul portları temizler, sanal ortamı otomatik başlatır ve tarayıcıda uygulamayı açar:

```bash
./run.sh
```

---

## Linux Masaüstü Kısayolu (.desktop) Kurulumu

Uygulamayı doğrudan masaüstünüzden veya uygulama menünüzden başlatmak için:

1. Proje içindeki `transkriptor_pro.desktop` dosyasını düzenleyerek `Exec` yolunun `./run.sh` dosyanızın mutlak yolu olduğundan emin olun.
2. Dosyayı uygulamalar dizinine kopyalayın:
   ```bash
   cp transkriptor_pro.desktop ~/.local/share/applications/
   ```
3. Çalıştırılabilir olarak işaretleyin:
   ```bash
   chmod +x ~/.local/share/applications/transkriptor_pro.desktop
   ```
Artık uygulama menünüzde "Transkriptör Pro" kısayolunu görebilirsiniz.
