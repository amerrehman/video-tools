param(
    [switch]$UseExternalExe,
    [switch]$NoWait,
    [int]$TimeoutSeconds = 600,
    [switch]$NoFallback,
    [string]$FallbackTargetDir,
    [string]$PlannedChangeSummary,
    [string]$PlannedChangeSummaryPath
)

$scriptPath = Join-Path $PSScriptRoot 'scripts\daily_backupper.ps1'
$invokeArgs = @{}

if ($UseExternalExe) { $invokeArgs.UseExternalExe = $true }
if ($NoWait) { $invokeArgs.NoWait = $true }
if ($PSBoundParameters.ContainsKey('TimeoutSeconds')) { $invokeArgs.TimeoutSeconds = $TimeoutSeconds }
if ($NoFallback) { $invokeArgs.NoFallback = $true }
if ($PSBoundParameters.ContainsKey('FallbackTargetDir')) { $invokeArgs.FallbackTargetDir = $FallbackTargetDir }
if ($PSBoundParameters.ContainsKey('PlannedChangeSummary')) { $invokeArgs.PlannedChangeSummary = $PlannedChangeSummary }
if ($PSBoundParameters.ContainsKey('PlannedChangeSummaryPath')) { $invokeArgs.PlannedChangeSummaryPath = $PlannedChangeSummaryPath }

& $scriptPath @invokeArgs
exit $LASTEXITCODE
