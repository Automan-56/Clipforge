# Setup environment for clipforge
# Run this script in PowerShell before using clipforge

$ffmpegPath = "$env:LOCALAPPDATA\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin"
if (Test-Path $ffmpegPath) {
    $env:PATH = "$ffmpegPath;$env:PATH"
    Write-Host "FFmpeg added to PATH for this session" -ForegroundColor Green
} else {
    Write-Host "FFmpeg not found at expected location" -ForegroundColor Red
}

# Activate virtual environment
$venvPath = ".venv\Scripts\Activate.ps1"
if (Test-Path $venvPath) {
    & $venvPath
    Write-Host "Virtual environment activated" -ForegroundColor Green
} else {
    Write-Host "Virtual environment not found" -ForegroundColor Red
}

Write-Host ""
Write-Host "You can now run: clipforge doctor" -ForegroundColor Cyan
