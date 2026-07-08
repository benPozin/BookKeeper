# Registers a Windows Task Scheduler entry that launches BookKeeper at login
# and restarts it automatically if it crashes. Run this once from an elevated
# PowerShell prompt (right-click PowerShell -> Run as administrator), from
# anywhere — it locates the project folder relative to this script.
#
#   powershell -ExecutionPolicy Bypass -File scripts\install_task.ps1

$ErrorActionPreference = "Stop"

$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$ScriptPath = Join-Path $ProjectRoot "scripts\start_bookkeeper.bat"

if (-not (Test-Path $ScriptPath)) {
    throw "Could not find $ScriptPath — run this script from inside the BookKeeper project."
}

$TaskName = "BookKeeper"
$Action = New-ScheduledTaskAction -Execute $ScriptPath
$Trigger = New-ScheduledTaskTrigger -AtLogOn
$Settings = New-ScheduledTaskSettingsSet `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries

Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger `
    -Settings $Settings -Description "Runs BookKeeper at login and keeps it running." `
    -Force | Out-Null

Write-Host "Installed the '$TaskName' scheduled task."
Write-Host "It will start automatically at your next login."
Write-Host "To start it right now instead of waiting: Start-ScheduledTask -TaskName '$TaskName'"
