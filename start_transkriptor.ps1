param(
    [switch]$NoBrowser
)

$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExe = "C:\Users\emirh\AppData\Local\Programs\Python\Python311\python.exe"
$braveExe = "C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe"
$appUrl = "http://127.0.0.1:5000"

function Test-Transkriptor {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $appUrl -TimeoutSec 2
        return $response.StatusCode -eq 200
    }
    catch {
        return $false
    }
}

if (-not (Test-Transkriptor)) {
    Start-Process `
        -FilePath $pythonExe `
        -ArgumentList "app.py" `
        -WorkingDirectory $projectDir `
        -WindowStyle Hidden

    $ready = $false
    for ($attempt = 0; $attempt -lt 40; $attempt++) {
        Start-Sleep -Milliseconds 500
        if (Test-Transkriptor) {
            $ready = $true
            break
        }
    }

    if (-not $ready) {
        Add-Type -AssemblyName PresentationFramework
        [System.Windows.MessageBox]::Show(
            "Transkriptor baslatilamadi. Lutfen proje klasorunu kontrol edin.",
            "Transkriptor"
        ) | Out-Null
        exit 1
    }
}

if (-not $NoBrowser) {
    Start-Process -FilePath $braveExe -ArgumentList $appUrl
}
