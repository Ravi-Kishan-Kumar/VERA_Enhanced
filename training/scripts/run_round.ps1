# Full training round on ALL currently labelled reviews, logged to reports/<name>.log.
#   powershell -ExecutionPolicy Bypass -File training\scripts\run_round.ps1 -Name round2
#
# Output is redirected by cmd.exe (not PowerShell pipes): Windows PowerShell converts native
# stderr lines (library warnings, progress bars) into error records and can abort the child.
param(
    [string]$Name = "round2",
    [string]$LabelRuns = "primary-a,primary-b,qwen-a,qwen-b,crossmodel-qwen"
)
$ErrorActionPreference = "Continue"
Set-Location (Join-Path $PSScriptRoot "..\..")
New-Item -ItemType Directory -Force reports | Out-Null
$log = "reports\$Name.log"
$python = ".venv\Scripts\python.exe"
Set-Content -Path $log -Value "[$(Get-Date -Format HH:mm)] starting $Name with label runs $LabelRuns" -Encoding utf8

cmd /c "$python -u training\scripts\train_all.py --stages labels --force --allow-non-human-reference --label-runs $LabelRuns >> $log 2>&1"
if ($LASTEXITCODE -ne 0) { Add-Content $log "labels stage FAILED ($LASTEXITCODE)"; exit 1 }

cmd /c "$python -u training\scripts\train_all.py --force --stages crossfit,final,aspects,fusion,calibrate,evaluate,report,diagnostics >> $log 2>&1"
if ($LASTEXITCODE -ne 0) { Add-Content $log "training pipeline FAILED ($LASTEXITCODE)"; exit 1 }

$snapshot = "reports\$Name"
New-Item -ItemType Directory -Force $snapshot | Out-Null
Get-ChildItem reports -File | Copy-Item -Destination $snapshot
Copy-Item data\models\*_export_report.json, data\models\conformal_qhat.json, data\labels\agreement_report.json $snapshot
Add-Content $log "[$(Get-Date -Format HH:mm)] $Name COMPLETE; reports snapshot in $snapshot"
