param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [object[]]$ForwardArgs
)

$scriptPath = Join-Path $PSScriptRoot 'scripts\github_publish_token.ps1'
& $scriptPath @ForwardArgs
exit $LASTEXITCODE
