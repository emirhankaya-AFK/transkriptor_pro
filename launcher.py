import subprocess
import time
import socket
import sys
import os
import webbrowser

# Set current working directory to the directory of launcher.py
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Define server configuration
HOST = "127.0.0.1"
PORT = 5000
URL = f"http://{HOST}:{PORT}"
BRAVE_PATH = r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"

def is_port_in_use(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((HOST, port)) == 0

# Check if port is already in use
port_in_use = is_port_in_use(PORT)

if not port_in_use:
    print("🚀 Transkriptor Pro sunucusu baslatiliyor...")
    
    # Configure PYTHONPATH to import packages correctly
    env = os.environ.copy()
    parent_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    env["PYTHONPATH"] = parent_dir + os.pathsep + env.get("PYTHONPATH", "")
    
    # Run Flask app in a new command window using cmd.exe /k to keep it open on failure
    subprocess.Popen(
        ["cmd.exe", "/k", sys.executable, "app.py"],
        env=env,
        creationflags=subprocess.CREATE_NEW_CONSOLE
    )
    
    # Wait for the port to open
    print("⏳ Sunucunun hazir olmasi bekleniyor...")
    for _ in range(25):
        if is_port_in_use(PORT):
            break
        time.sleep(0.2)
else:
    print("ℹ️ Port 5000 zaten kullanimda. Uygulama zaten calisiyor olabilir.")

# Open in Brave Browser if available
if os.path.exists(BRAVE_PATH):
    print(f"🌐 Tarayici aciliyor (Brave): {URL}")
    subprocess.Popen([BRAVE_PATH, URL])
else:
    print(f"🌐 Varsayilan tarayici aciliyor: {URL}")
    webbrowser.open(URL)
