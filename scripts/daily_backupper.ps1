param(
    # Use the external Daily Backupper.exe. Default is the internal ZIP backup path because the EXE is unreliable.
    [switch]$UseExternalExe,

    # If set, we will just launch the EXE and return immediately.
    [switch]$NoWait,

    # Max time to wait for the EXE to finish when not using -NoWait.
    [int]$TimeoutSeconds = 600,

    # Disable the repo-local ZIP fallback.
    [switch]$NoFallback,

    # Where to write fallback backups (only used when the EXE fails).
    [string]$FallbackTargetDir = (Join-Path (Split-Path -Parent $PSScriptRoot) 'Daily Backups'),

    # Optional human-written note describing the planned work this backup is protecting.
    [string]$PlannedChangeSummary,

    # Optional file containing the planned-change summary.
    [string]$PlannedChangeSummaryPath = (Join-Path (Split-Path -Parent $PSScriptRoot) '.backup_planned_changes.txt')
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$backupExe = "C:\Users\Amer\OneDrive\Documents\Python Scripts\Bot Files Updater\dist\Daily Backupper.exe"
$projectDir = Split-Path -Parent $PSScriptRoot

function Resolve-PlannedChangeSummary {
    param(
        [string]$ExplicitSummary,
        [string]$SummaryFilePath
    )

    if (-not [string]::IsNullOrWhiteSpace($ExplicitSummary)) {
        return $ExplicitSummary.Trim()
    }

    $envCandidates = @(
        $env:CODEX_PLANNED_CHANGE_SUMMARY,
        $env:PLANNED_CHANGE_SUMMARY,
        $env:BACKUP_PLANNED_CHANGE_SUMMARY
    )
    foreach ($candidate in $envCandidates) {
        if (-not [string]::IsNullOrWhiteSpace($candidate)) {
            return $candidate.Trim()
        }
    }

    if (-not [string]::IsNullOrWhiteSpace($SummaryFilePath) -and (Test-Path -LiteralPath $SummaryFilePath)) {
        try {
            $content = (Get-Content -LiteralPath $SummaryFilePath -Raw -ErrorAction Stop).Trim()
            if (-not [string]::IsNullOrWhiteSpace($content)) {
                return $content
            }
        }
        catch {
        }
    }

    return $null
}

function Set-ZipFileComment {
    param(
        [Parameter(Mandatory = $true)][string]$ZipPath,
        [Parameter(Mandatory = $true)][string]$Comment
    )

    if (-not (Test-Path -LiteralPath $ZipPath)) {
        throw "ZIP not found: $ZipPath"
    }

    $encoding = New-Object System.Text.UTF8Encoding($false)

    # ZIP comment length is a uint16 (max 65535 bytes).
    $maxBytes = 65535
    $commentText = if ($null -eq $Comment) { '' } else { [string]$Comment }
    $commentBytes = $encoding.GetBytes($commentText)
    if ($commentBytes.Length -gt $maxBytes) {
        # Truncate safely (avoid splitting UTF-8 sequences) via binary search on string length.
        $lo = 0
        $hi = $commentText.Length
        while ($lo -lt $hi) {
            $mid = [int][Math]::Ceiling(($lo + $hi) / 2.0)
            $b = $encoding.GetBytes($commentText.Substring(0, $mid))
            if ($b.Length -le $maxBytes) { $lo = $mid } else { $hi = $mid - 1 }
        }
        $commentBytes = $encoding.GetBytes($commentText.Substring(0, $lo))
    }

    $fileInfo = Get-Item -LiteralPath $ZipPath
    $fileLen = [int64]$fileInfo.Length
    $minLen = 22
    if ($fileLen -lt $minLen) {
        throw "Invalid ZIP (too small): $ZipPath"
    }

    $maxSearch = [int64]([Math]::Min($fileLen, 22 + $maxBytes))
    $tail = New-Object byte[] ([int]$maxSearch)
    $fs = [System.IO.File]::Open($ZipPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    try {
        [void]$fs.Seek(-$maxSearch, [System.IO.SeekOrigin]::End)
        $read = 0
        while ($read -lt $tail.Length) {
            $n = $fs.Read($tail, $read, $tail.Length - $read)
            if ($n -le 0) { break }
            $read += $n
        }
        if ($read -ne $tail.Length) {
            throw "Failed to read ZIP tail for comment injection: $ZipPath"
        }
    }
    finally { $fs.Dispose() }

    # Find End Of Central Directory (EOCD) signature: 0x06054b50 (bytes 50 4b 05 06).
    $sig0 = 0x50
    $sig1 = 0x4b
    $sig2 = 0x05
    $sig3 = 0x06
    $eocdInTail = -1
    for ($i = $tail.Length - 22; $i -ge 0; $i--) {
        if ($tail[$i] -eq $sig0 -and $tail[$i + 1] -eq $sig1 -and $tail[$i + 2] -eq $sig2 -and $tail[$i + 3] -eq $sig3) {
            $eocdInTail = $i
            break
        }
    }
    if ($eocdInTail -lt 0) {
        throw "EOCD not found; cannot set ZIP comment: $ZipPath"
    }

    $eocdOffset = $fileLen - $tail.Length + $eocdInTail
    $eocdLen = 22

    $tmpPath = "$ZipPath.tmp"
    if (Test-Path -LiteralPath $tmpPath) { Remove-Item -LiteralPath $tmpPath -Force }

    $inStream = [System.IO.File]::Open($ZipPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::Read)
    $outStream = [System.IO.File]::Open($tmpPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
    try {
        $buffer = New-Object byte[] 131072
        $remaining = $eocdOffset
        while ($remaining -gt 0) {
            $toRead = [int][Math]::Min($buffer.Length, $remaining)
            $n = $inStream.Read($buffer, 0, $toRead)
            if ($n -le 0) { throw "Unexpected EOF copying ZIP: $ZipPath" }
            $outStream.Write($buffer, 0, $n)
            $remaining -= $n
        }

        $eocd = New-Object byte[] $eocdLen
        $n2 = $inStream.Read($eocd, 0, $eocdLen)
        if ($n2 -ne $eocdLen) { throw "Unexpected EOF reading EOCD: $ZipPath" }

        $commentLen = [UInt16]$commentBytes.Length
        $eocd[20] = [byte]($commentLen -band 0xFF)
        $eocd[21] = [byte](($commentLen -shr 8) -band 0xFF)
        $outStream.Write($eocd, 0, $eocdLen)

        # Ignore any existing comment; replace it with our comment bytes.
        $outStream.Write($commentBytes, 0, $commentBytes.Length)
    }
    finally {
        $inStream.Dispose()
        $outStream.Dispose()
    }

    try {
        # In this OneDrive-backed folder, rename/replace operations can fail with access denied
        # even though a byte-for-byte overwrite succeeds.
        Copy-Item -LiteralPath $tmpPath -Destination $ZipPath -Force
    }
    finally {
        if (Test-Path -LiteralPath $tmpPath) {
            Remove-Item -LiteralPath $tmpPath -Force -ErrorAction SilentlyContinue
        }
    }
}

function New-BackupComment {
    param(
        [Parameter(Mandatory = $true)][string]$SourcePath,
        [Parameter(Mandatory = $true)][string]$Stamp,
        [Parameter(Mandatory = $true)][object[]]$IncludedFiles,
        [datetime]$PreviousBackupTime,
        [string]$PlannedChangeSummary
    )

    $lines = New-Object 'System.Collections.Generic.List[string]'
    $lines.Add("Backup created: $Stamp")
    $lines.Add("Project: $SourcePath")

    $plannedSummary = if ([string]::IsNullOrWhiteSpace($PlannedChangeSummary)) { $null } else { $PlannedChangeSummary.Trim() }
    if ($plannedSummary) {
        $lines.Add("Planned changes:")
        $lines.Add($plannedSummary)
        return ($lines -join "`n")
    }

    if ($PreviousBackupTime) {
        $baselineLabel = $PreviousBackupTime.ToString('yyyy-MM-dd HH:mm:ss')
        $lines.Add("Backup purpose: safety snapshot before upcoming implementation work.")
        $lines.Add("Planned changes: not provided to the backup launcher.")
        $lines.Add("Previous backup: $baselineLabel")
    }
    else {
        $lines.Add("Backup purpose: safety snapshot before upcoming implementation work.")
        $lines.Add("Planned changes: not provided to the backup launcher.")
        $lines.Add("Previous backup: none found")
    }

    return ($lines -join "`n")
}

function New-RepoZipBackup {
    param(
        [Parameter(Mandatory = $true)][string]$SourceDir,
        [Parameter(Mandatory = $true)][string]$TargetDir,
        [Parameter(Mandatory = $true)][string]$Stamp
    )

    # ZipArchiveMode lives in System.IO.Compression; ZipFile lives in System.IO.Compression.FileSystem.
    Add-Type -AssemblyName System.IO.Compression | Out-Null
    Add-Type -AssemblyName System.IO.Compression.FileSystem | Out-Null

    $excludeDirs = @(
        '__pycache__',
        'build',
        'dist',
        '.sync',
        'Logs',
        'Images',
        'Assets',
        '.venv'
    )
    $excludeSet = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($d in $excludeDirs) { [void]$excludeSet.Add($d) }

    $srcPath = (Resolve-Path -LiteralPath $SourceDir).Path.TrimEnd('\')
    $srcName = Split-Path -Leaf $srcPath

    New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
    $zipPath = Join-Path $TargetDir ("{0} Backup {1}.zip" -f $srcName, $Stamp)
    $targetPath = (Resolve-Path -LiteralPath $TargetDir).Path.TrimEnd('\')
    $previousBackup = Get-ChildItem -LiteralPath $TargetDir -Filter ("{0} Backup *.zip" -f $srcName) -File -ErrorAction SilentlyContinue |
        Sort-Object LastWriteTime -Descending |
        Select-Object -First 1
    $previousBackupTime = $null
    if ($null -ne $previousBackup) {
        $previousBackupTime = $previousBackup.LastWriteTime
    }

    # Create fresh each time.
    if (Test-Path -LiteralPath $zipPath) { Remove-Item -LiteralPath $zipPath -Force }

    $zip = [System.IO.Compression.ZipFile]::Open($zipPath, [System.IO.Compression.ZipArchiveMode]::Create)
    try {
        $files = Get-ChildItem -LiteralPath $srcPath -Recurse -File -Force
        $includedFiles = New-Object 'System.Collections.Generic.List[object]'
        foreach ($f in $files) {
            $full = $f.FullName

            # Never try to include the fallback ZIP (or anything else in the fallback target folder),
            # otherwise we can deadlock on the in-progress ZIP file handle.
            if ($full -eq $zipPath) { continue }
            if ($full.StartsWith($targetPath + '\', [System.StringComparison]::OrdinalIgnoreCase)) { continue }

            $rel = $full.Substring($srcPath.Length).TrimStart('\')
            if (-not $rel) { continue }

            $parts = $rel -split '\\'
            $skip = $false
            foreach ($p in $parts) {
                if ($excludeSet.Contains($p)) { $skip = $true; break }
            }
            if ($skip) { continue }

            $entryName = Join-Path $srcName $rel
            [System.IO.Compression.ZipFileExtensions]::CreateEntryFromFile(
                $zip,
                $full,
                $entryName,
                [System.IO.Compression.CompressionLevel]::Optimal
            ) | Out-Null
            [void]$includedFiles.Add([pscustomobject]@{
                RelativePath = $rel
                LastWriteTime = $f.LastWriteTime
            })
        }

        $resolvedSummary = Resolve-PlannedChangeSummary -ExplicitSummary $PlannedChangeSummary -SummaryFilePath $PlannedChangeSummaryPath
        $notes = New-BackupComment -SourcePath $srcPath -Stamp $Stamp -IncludedFiles $includedFiles.ToArray() -PreviousBackupTime $previousBackupTime -PlannedChangeSummary $resolvedSummary
    }
    finally {
        $zip.Dispose()
    }

    try {
        Set-ZipFileComment -ZipPath $zipPath -Comment $notes
    }
    catch {
        Write-Warning ("Failed to set ZIP comment for {0}: {1}" -f $zipPath, $_.Exception.Message)
    }

    try {
        $backupPattern = "{0} Backup *.zip" -f $srcName
        $oldBackups = Get-ChildItem -LiteralPath $TargetDir -Filter $backupPattern -File -ErrorAction SilentlyContinue |
            Sort-Object LastWriteTime -Descending
        if ($oldBackups.Count -gt 10) {
            foreach ($old in ($oldBackups | Select-Object -Skip 10)) {
                Remove-Item -LiteralPath $old.FullName -Force -ErrorAction SilentlyContinue
            }
        }
    }
    catch {
        Write-Warning ("Failed to prune old backups in {0}: {1}" -f $TargetDir, $_.Exception.Message)
    }

    return $zipPath
}

if (-not $UseExternalExe) {
    $stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
    $zip = New-RepoZipBackup -SourceDir $projectDir -TargetDir $FallbackTargetDir -Stamp $stamp
    Write-Output ("Internal backup created at: {0}" -f $zip)
    exit 0
}

if (-not (Test-Path -LiteralPath $backupExe)) {
    Write-Warning "Backup executable not found: $backupExe"
    if (-not $NoFallback) {
        $stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
        $zip = New-RepoZipBackup -SourceDir $projectDir -TargetDir $FallbackTargetDir -Stamp $stamp
        Write-Output ("Fallback backup created at: {0}" -f $zip)
        exit 0
    }
    exit 1
}

$exeDir = Split-Path -Parent $backupExe
$logDir = Join-Path $projectDir 'Logs\DailyBackupper'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format 'yyyy-MM-dd_HH-mm-ss'
$stdoutPath = Join-Path $logDir ("stdout_{0}.log" -f $stamp)
$stderrPath = Join-Path $logDir ("stderr_{0}.log" -f $stamp)

try {
    $proc = Start-Process `
        -FilePath $backupExe `
        -WorkingDirectory $exeDir `
        -WindowStyle Hidden `
        -RedirectStandardOutput $stdoutPath `
        -RedirectStandardError $stderrPath `
        -PassThru
}
catch {
    Write-Warning ("Failed to start Daily Backupper.exe: {0}" -f $_.Exception.Message)
    if (-not $NoFallback) {
        $zip = New-RepoZipBackup -SourceDir $projectDir -TargetDir $FallbackTargetDir -Stamp $stamp
        Write-Output ("Fallback backup created at: {0}" -f $zip)
        exit 0
    }
    Write-Output "Fallback disabled (-NoFallback). No backup was created."
    exit 1
}

Write-Output ("Started Daily Backupper.exe (PID={0})" -f $proc.Id)
Write-Output ("Logs: {0} , {1}" -f $stdoutPath, $stderrPath)

if ($NoWait) {
    exit 0
}

if (-not $proc.WaitForExit($TimeoutSeconds * 1000)) {
    try { $proc.Kill() } catch { }
    Write-Warning ("Daily Backupper.exe timed out after {0}s (PID={1})." -f $TimeoutSeconds, $proc.Id)
    if (-not $NoFallback) {
        $zip = New-RepoZipBackup -SourceDir $projectDir -TargetDir $FallbackTargetDir -Stamp $stamp
        Write-Output ("Fallback backup created at: {0}" -f $zip)
        exit 0
    }
    Write-Output "Fallback disabled (-NoFallback). No backup was created."
    exit 1
}

if ($proc.ExitCode -ne 0) {
    $exitCode = if ($null -eq $proc.ExitCode) { -1 } else { [int]$proc.ExitCode }
    $tail = ''
    if (Test-Path -LiteralPath $stderrPath) {
        $tail = (Get-Content -LiteralPath $stderrPath -ErrorAction SilentlyContinue -Tail 40) -join "`n"
    }
    if ($tail) {
        Write-Warning ("Daily Backupper.exe failed (exit {0}). stderr tail:`n{1}" -f $exitCode, $tail)
    }
    else {
        Write-Warning ("Daily Backupper.exe failed (exit {0}). See logs: {1}" -f $exitCode, $logDir)
    }

    if (-not $NoFallback) {
        $zip = New-RepoZipBackup -SourceDir $projectDir -TargetDir $FallbackTargetDir -Stamp $stamp
        Write-Output ("Fallback backup created at: {0}" -f $zip)
        exit 0
    }

    Write-Output "Fallback disabled (-NoFallback). No backup was created."
    exit 1
}

# Best-effort confirmation: parse stdout for the path the EXE prints on success.
$confirmedPath = $null
if (Test-Path -LiteralPath $stdoutPath) {
    $m = Select-String -LiteralPath $stdoutPath -Pattern 'Backup created at:\s*(.+)$' -AllMatches -ErrorAction SilentlyContinue | Select-Object -Last 1
    if ($m -and $m.Matches -and $m.Matches.Count -gt 0) {
        $confirmedPath = $m.Matches[0].Groups[1].Value.Trim()
    }
}

if ($confirmedPath -and (Test-Path -LiteralPath $confirmedPath)) {
    Write-Output ("Backup created at: {0}" -f $confirmedPath)
}
else {
    Write-Output "Daily Backupper.exe exited successfully, but the backup file path could not be confirmed from stdout. Check the logs above for details."
}


