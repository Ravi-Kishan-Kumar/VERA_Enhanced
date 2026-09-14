# Wait for enough labels (or a deadline), then run the full training pipeline once.
#   powershell -ExecutionPolicy Bypass -File training\scripts\auto_train_round.ps1 -MinLabels 1000 -MaxWaitMinutes 75
param(
    [int]$MinLabels = 1000,
    [int]$MaxWaitMinutes = 75,
    [string]$LabelRuns = "primary-a,qwen-a,crossmodel-qwen"
)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..\..")
$python = ".\.venv\Scripts\python.exe"
$deadline = (Get-Date).AddMinutes($MaxWaitMinutes)

$countScript = @"
import json, pathlib
ids = set()
for run in '$LabelRuns'.split(','):
    path = pathlib.Path('data/labels') / f'run_{run}.json'
    if path.exists():
        ids |= set(json.loads(path.read_text(encoding='utf-8'))['labels'])
print(len(ids))
"@

while ($true) {
    $count = [int](& $python -c $countScript)
    Write-Output "[$(Get-Date -Format HH:mm)] labeled reviews: $count"
    if ($count -ge $MinLabels -or (Get-Date) -ge $deadline) { break }
    Start-Sleep -Seconds 120
}

Write-Output "[$(Get-Date -Format HH:mm)] starting training round on $count labeled reviews"
& $python training\scripts\train_all.py --stages labels --force --allow-non-human-reference --label-runs $LabelRuns
if ($LASTEXITCODE -ne 0) { throw "labels stage failed" }
& $python training\scripts\train_all.py --stages crossfit,final,fusion,calibrate,evaluate,report
if ($LASTEXITCODE -ne 0) { throw "training pipeline failed" }
Write-Output "[$(Get-Date -Format HH:mm)] TRAINING ROUND COMPLETE"
