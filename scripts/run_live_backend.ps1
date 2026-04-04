$ErrorActionPreference = "Stop"

$root = "C:\Users\Administrator\Desktop\Mutiagent\backend"
$storageRoot = Join-Path $root "storage\demo-run"
$uploads = Join-Path $storageRoot "live-backend-uploads"

New-Item -ItemType Directory -Force -Path $storageRoot | Out-Null
New-Item -ItemType Directory -Force -Path $uploads | Out-Null

$env:DATABASE_URL = "sqlite:///C:/Users/Administrator/Desktop/Mutiagent/backend/storage/demo-run/live-backend.db"
$env:VECTOR_STORE = "local"
$env:QDRANT_URL = ""
$env:FILE_STORAGE_PATH = "C:/Users/Administrator/Desktop/Mutiagent/backend/storage/demo-run/live-backend-uploads"
$env:SEARCH_ENABLED = "true"
$env:SEARCH_PROVIDER = "duckduckgo"

Set-Location $root
& ".\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8000
