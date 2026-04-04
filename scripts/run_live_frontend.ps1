$ErrorActionPreference = "Stop"

$root = "C:\Users\Administrator\Desktop\Mutiagent\frontend"

Set-Location $root
& "npm.cmd" run dev -- --host 127.0.0.1 --port 5173
