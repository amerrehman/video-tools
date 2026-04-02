param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [object[]]$ForwardArgs
)

$scriptPath = Join-Path $PSScriptRoot 'scripts\daily_backupper.ps1'
& $scriptPath @ForwardArgs
exit $LASTEXITCODE
