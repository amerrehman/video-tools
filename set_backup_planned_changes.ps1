param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [object[]]$ForwardArgs
)

$scriptPath = Join-Path $PSScriptRoot 'scripts\backup_planned_changes.ps1'
& $scriptPath @ForwardArgs
exit $LASTEXITCODE
