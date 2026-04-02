param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$SummaryParts,

    [switch]$Clear
)

$scriptPath = Join-Path $PSScriptRoot 'scripts\backup_planned_changes.ps1'
$invokeArgs = @{}

if ($SummaryParts) { $invokeArgs.SummaryParts = $SummaryParts }
if ($Clear) { $invokeArgs.Clear = $true }

& $scriptPath @invokeArgs
exit $LASTEXITCODE
