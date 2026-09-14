# Live VERA progress dashboard (refreshes every 30 s; Ctrl+C to exit).
#   powershell -ExecutionPolicy Bypass -File training\scripts\watch_progress.ps1
param([int]$IntervalSeconds = 30)
Set-Location (Join-Path $PSScriptRoot "..\..")
$python = ".\.venv\Scripts\python.exe"
# Where Claude's session writes the auto-training log (newest task output mentioning the round).
$taskDir = Join-Path $env:LOCALAPPDATA "Temp\claude"

while ($true) {
    Clear-Host
    Write-Host "VERA progress  $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor Cyan
    Write-Host "`n== Labels ==" -ForegroundColor Yellow
    & $python training\scripts\label_status.py

    Write-Host "`n== Training log (latest lines) ==" -ForegroundColor Yellow
    $log = Get-ChildItem $taskDir -Recurse -Filter *.output -ErrorAction SilentlyContinue |
        Where-Object { Select-String -Path $_.FullName -Pattern "labeled reviews:|=== \w+ ===" -Quiet } |
        Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($log) { Get-Content $log.FullName -Tail 12 } else { Write-Host "(no training log yet)" }

    Write-Host "`n== Reports ==" -ForegroundColor Yellow
    foreach ($name in "experience_oof.json", "experience_export.json", "fusion_holdout.json",
                      "calibration.json", "cv_comparison.json", "evaluation_report.json") {
        $path = Join-Path "reports" $name
        $state = if (Test-Path $path) { "done  $((Get-Item $path).LastWriteTime.ToString('HH:mm'))" } else { "pending" }
        Write-Host ("{0,-26} {1}" -f $name, $state)
    }

    Write-Host "`n== GPU ==" -ForegroundColor Yellow
    nvidia-smi --query-gpu=utilization.gpu,memory.used,memory.total,temperature.gpu --format=csv,noheader
    Start-Sleep -Seconds $IntervalSeconds
}
