# Transkriptor Pro — YouTube Transcript and AI Summary Assistant [UPGRADED]

[English](#english) | [Türkçe](#türkçe) | [Deutsch](#deutsch)

## English

**Purpose**  
Flask application that retrieves YouTube captions, generates summaries and structured study notes, and detects videos from pasted or uploaded screenshots using multimodal AI and OCR.

**Features**  
- Transcript retrieval from a YouTube URL or video ID  
- Screenshot analysis for video titles and channel names  
- Gemini model fallback and retry chain  
- Local extractive summarizer when AI is unavailable  
- OCR.space fallback for image text extraction  
- Persistent SQLite cache  
- Responsive light/dark interface  
- Timestamp links, clipboard copy, and text download  

**Stack**  
- Python 3.12+  
- Flask (app.py, routes/, services/)  
- Dependencies listed in requirements.txt  
- SQLite database (database.py)  
- Optional OCR.space API  
- Optional Gemini API  

**Setup**  
```bash
python -m venv venv
pip install -r requirements.txt
```
Create a `.env` file from `.env.example` and add:  
```
GEMINI_API_KEY=your_key
OCR_SPACE_KEY=your_optional_key  
```
Never commit the `.env` file.

**Usage**  
```bash
python app.py
```
Open `http://127.0.0.1:5000`.  
Platform‑specific launchers are provided: `run.sh` (Linux/macOS), `run.bat` and `start_transkriptor.ps1` (Windows).

**Testing**  
Unit tests exist in the `tests/` directory (e.g., `test_workflow.py`). Run them with `pytest` or `python -m unittest`.

**Limitations**  
- Requires internet access to fetch YouTube captions.  
- AI summarization depends on a valid Gemini API key.  
- OCR extraction requires an OCR_SPACE_KEY (optional).  
- The local extractive summarizer is a fallback and may be less accurate than the AI models.  

## Türkçe

**Amaç**  
YouTube altyazılarını alır, özet ve çalışma notları üretir, ekran görüntülerinden OCR ve çoklu modal AI ile video tespiti yapan Flask uygulaması.

**Özellikler**  
- YouTube URL veya video ID'den transkript alma  
- Ekran görüntüsü analizi ile video başlığı ve kanal adı tespiti  
- Gemini modeli yedekleme ve yeniden deneme zinciri  
- AI kullanılamadığında yerel çıkarımsal özetleyici  
- OCR.space yedekli görüntü metin çıkarma  
- Kalıcı SQLite önbelleği  
- Yanıltıcı olmayan açık/koyu tema  
- Zaman damgası bağlantıları, panoya kopyalama, metin indirme  

**Yığın**  
- Python 3.12+  
- Flask (app.py, routes/, services/)  
- Bağımlılıklar requirements.txt'te  
- SQLite veritabanı (database.py)  
- İsteğe bağlı OCR.space API  
- İsteğe bağlı Gemini API  

**Kurulum**  
```bash
python -m venv venv
pip install -r requirements.txt
```
`.env.example` dosyasından `.env` oluşturup şu değişkenleri ekleyin:  
```
GEMINI_API_KEY=your_key
OCR_SPACE_KEY=your_optional_key  
```
`.env` dosyasını asla commit etmeyin.

**Kullanım**  
```bash
python app.py
```
Tarayıcıda `http://127.0.0.1:5000` adresini açın.  
Linux/macOS için `./run.sh`, Windows için `run.bat` veya `start_transkriptor.ps1` kullanılabilir.

**Test**  
`tests/` klasöründeki birim testleri (örneğin `test_workflow.py`) `pytest` veya `python -m unittest` ile çalıştırabilirsiniz.

**Sınırlamalar**  
- YouTube altyazısı çekimi için internet gerekir.  
- AI özetleme Gemini API anahtarına bağlıdır.  
- OCR işlemi OCR_SPACE_KEY gerektirir (isteğe bağlı).  
- Yerel çıkarımsal özetleyici yedek bir çözümdür ve AI modellerinden daha az doğru olabilir.  

## Deutsch

**Zweck**  
Eine Flask-Anwendung, die YouTube-Untertitel abruft, Zusammenfassungen und Lernnotizen erstellt und Videos anhand von Screenshots mittels OCR und multimodaler KI erkennt.

**Funktionen**  
- Transkriptabruf aus einer YouTube-URL oder Video-ID  
- Screenshotanalyse für Videotitel und Kanalnamen  
- Gemini-Modell-Fallback und Wiederholungsmechanismus  
- Lokaler extraktiver Zusammenfassungsgenerator, falls KI nicht verfügbar ist  
- OCR.space-Fallback für Texterkennung in Bildern  
- Persistenter SQLite-Cache  
- Responsives helles/dunkles Interface  
- Zeitstempel-Links, Kopieren in die Zwischenablage und Textdownload  

**Stack**  
- Python 3.12+  
- Flask (app.py, routes/, services/)  
- Abhängigkeiten in requirements.txt  
- SQLite-Datenbank (database.py)  
- Optionale OCR.space API  
- Optionale Gemini API  

**Installation**  
```bash
python -m venv venv
pip install -r requirements.txt
```
Eine .env-Datei aus .env.example erstellen und folgende Variablen hinzufügen:  
```
GEMINI_API_KEY=your_key
OCR_SPACE_KEY=your_optional_key  
```
Die .env-Datei niemals committen.

**Ausführung**  
```bash
python app.py
```
Im Browser `http://127.0.0.1:5000` öffnen.  
Linux/macOS-Nutzer können `./run.sh` verwenden; Windows-Nutzer haben `run.bat` und `start_transkriptor.ps1` zur Verfügung.

**Tests**  
Einheitstests befinden sich im `tests/` Ordner (z. B. `test_workflow.py`) und können mit `pytest` oder `python -m unittest` ausgeführt werden.

**Einschränkungen**  
- Der Abruf von YouTube-Untertiteln benötigt eine Internetverbindung.  
- Die KI-Zusammenfassung setzt einen gültigen Gemini-API-Schlüssel voraus.  
- Die OCR-Funktion benötigt einen OCR_SPACE_KEY (optional).  
- Der lokale extraktive Zusammenfassungsgenerator dient nur als Fallback und kann weniger genau sein als die KI-Modelle.
