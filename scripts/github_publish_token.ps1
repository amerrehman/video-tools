$ErrorActionPreference = "Stop"

$envName = "VIDEO_TOOLS_GITHUB_TOKEN"

Write-Host "Enter a fresh GitHub token for Video Tools publishing." -ForegroundColor Cyan
Write-Host "This stores the token in your user environment so future PowerShell sessions can use the builder directly." -ForegroundColor DarkGray

$secure = Read-Host "GitHub token" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)

try {
    $token = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
}
finally {
    if ($bstr -ne [IntPtr]::Zero) {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
    }
}

if ([string]::IsNullOrWhiteSpace($token)) {
    throw "Token entry was empty. Nothing was saved."
}

[Environment]::SetEnvironmentVariable($envName, $token, "User")
$env:$envName = $token

Write-Host ""
Write-Host "Saved $envName for the current user." -ForegroundColor Green
Write-Host "Open a new PowerShell window before your next build, or keep using this one." -ForegroundColor DarkGray
