$iscc = Get-Command iscc -ErrorAction SilentlyContinue
if (-not $iscc) {
    $knownPaths = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    )
    $knownPath = $knownPaths | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($knownPath) {
        $iscc = @{ Source = $knownPath }
    } else {
        throw "Inno Setup is not installed. Install it from https://jrsoftware.org/isinfo.php and run this script again."
    }
}

$projectRoot = Split-Path -Parent $PSScriptRoot
& $iscc.Source (Join-Path $PSScriptRoot "CS2Trening.iss")
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE."
}
Write-Host "Installer created in $projectRoot\dist\installer"
