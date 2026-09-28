<#
.SYNOPSIS
    Cross-platform PowerShell wrapper for Telegram Bot Manager CLI.
.DESCRIPTION
    Runs scripts/telegram_cli.py using available python3 or python interpreter.
.EXAMPLE
    .\run.ps1 auth status
    .\run.ps1 send message --chat-id 123456789 --text "Hello from PowerShell"
#>

[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$ScriptArgs
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$cliPath = Join-Path $scriptDir "telegram_cli.py"

# Find python executable
$pythonExe = $null
if (Get-Command "python" -ErrorAction SilentlyContinue) {
    $pythonExe = "python"
} elseif (Get-Command "python3" -ErrorAction SilentlyContinue) {
    $pythonExe = "python3"
} elseif (Get-Command "py" -ErrorAction SilentlyContinue) {
    $pythonExe = "py"
} else {
    Write-Error "Python 3 is required to run Telegram Bot Manager CLI. Please install Python."
    exit 1
}

& $pythonExe $cliPath @ScriptArgs
exit $LASTEXITCODE
