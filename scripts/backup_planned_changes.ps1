param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$SummaryParts,

    [switch]$Clear
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$notePath = Join-Path (Split-Path -Parent $PSScriptRoot) '.backup_planned_changes.txt'

if ($Clear) {
    if (Test-Path -LiteralPath $notePath) {
        Remove-Item -LiteralPath $notePath -Force
        Write-Output ("Cleared backup planned-change note: {0}" -f $notePath)
    }
    else {
        Write-Output ("No backup planned-change note to clear: {0}" -f $notePath)
    }
    exit 0
}

$summary = (($SummaryParts | Where-Object { -not [string]::IsNullOrWhiteSpace($_) }) -join ' ').Trim()
if ([string]::IsNullOrWhiteSpace($summary)) {
    Write-Error "Provide a summary, or use -Clear."
    exit 1
}

Set-Content -LiteralPath $notePath -Value $summary -Encoding UTF8
Write-Output ("Saved backup planned-change note: {0}" -f $notePath)
Write-Output ("Summary: {0}" -f $summary)


