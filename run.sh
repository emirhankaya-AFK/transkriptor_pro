#!/bin/bash

# Port kontrolü
PORT=5000
echo "🚀 Transkriptör Pro başlatılıyor..."

# Portu kullanan süreci bul ve sonlandır
PID=$(lsof -t -i:$PORT)
if [ ! -z "$PID" ]; then
    echo "⚠️ $PORT portu zaten kullanımda (PID: $PID). Eski süreç sonlandırılıyor..."
    kill -9 $PID
    sleep 1
fi

# Betiğin bulunduğu dizine geç
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

# Sanal ortam (venv) kontrolü ve kurulumu
if [ ! -d "venv" ]; then
    echo "📦 Sanal ortam (venv) bulunamadı. Oluşturuluyor..."
    python3 -m venv venv
    source venv/bin/activate
    echo "📥 Bağımlılıklar yükleniyor (requirements.txt)..."
    pip install --upgrade pip
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Flask uygulamasını arka planda başlat
export PYTHONPATH="$DIR/.."
python3 app.py > app.log 2>&1 &
APP_PID=$!

echo "⚙️ Flask uygulaması arka planda başlatıldı (PID: $APP_PID). Loglar 'app.log' dosyasına yazılıyor."
sleep 2

# Uygulamanın çalışıp çalışmadığını kontrol et ve tarayıcıda aç
if kill -0 $APP_PID >/dev/null 2>&1; then
    URL="http://127.0.0.1:5000"
    echo "🌐 Tarayıcı açılıyor: $URL"
    
    if which xdg-open > /dev/null; then
        xdg-open "$URL"
    elif type gnome-open > /dev/null; then
        gnome-open "$URL"
    elif type open > /dev/null; then
        open "$URL"
    else
        echo "ℹ️ Lütfen tarayıcınızdan $URL adresini manuel olarak açın."
    fi
else
    echo "❌ Uygulama başlatılamadı. Hata detayı için 'app.log' dosyasını kontrol edin:"
    cat app.log
fi
