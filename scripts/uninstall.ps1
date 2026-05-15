$ErrorActionPreference = "Stop"

$InstallDir = if ($env:HICLAW_INSTALL_DIR) { $env:HICLAW_INSTALL_DIR } else { Join-Path $env:LOCALAPPDATA "HiClaw\hiclaw-py" }
$BinDir = if ($env:HICLAW_BIN_DIR) { $env:HICLAW_BIN_DIR } else { Join-Path $env:USERPROFILE ".hiclaw\bin" }
$KeepData = $env:HICLAW_KEEP_DATA -eq "1"

function Write-Step {
    param([string]$Message)
    Write-Host "==> $Message" -ForegroundColor Cyan
}

function Write-Warn {
    param([string]$Message)
    Write-Host "Warning: $Message" -ForegroundColor Yellow
}

function Remove-PathIfExists {
    param([string]$Path)
    if (Test-Path $Path) {
        Remove-Item -LiteralPath $Path -Recurse -Force
        Write-Host "Removed $Path"
    }
}

function Remove-UserPathEntry {
    param([string]$PathToRemove)
    $currentPath = [Environment]::GetEnvironmentVariable("Path", "User")
    if ([string]::IsNullOrWhiteSpace($currentPath)) {
        return
    }
    $parts = $currentPath -split ";" | Where-Object { $_ -and ($_ -ne $PathToRemove) }
    $newPath = ($parts -join ";")
    if ($newPath -ne $currentPath) {
        [Environment]::SetEnvironmentVariable("Path", $newPath, "User")
        $env:Path = (($env:Path -split ";") | Where-Object { $_ -and ($_ -ne $PathToRemove) }) -join ";"
        Write-Host "Removed $PathToRemove from the user PATH"
    }
}

function Main {
    Write-Step "Uninstalling HiClaw"

    Remove-PathIfExists (Join-Path $BinDir "hiclaw.cmd")
    Remove-PathIfExists (Join-Path $BinDir "hiclaw-tui.cmd")
    Remove-PathIfExists (Join-Path $BinDir "hiclaw-dashboard.cmd")
    Remove-PathIfExists (Join-Path $BinDir "hiclaw-feishu.cmd")

    if ($KeepData) {
        Write-Warn "Keeping install directory because HICLAW_KEEP_DATA=1: $InstallDir"
    } else {
        Remove-PathIfExists $InstallDir
        $parent = Split-Path -Parent $InstallDir
        if ((Test-Path $parent) -and -not (Get-ChildItem -LiteralPath $parent -Force -ErrorAction SilentlyContinue)) {
            Remove-Item -LiteralPath $parent -Force
            Write-Host "Removed $parent"
        }
    }

    Remove-UserPathEntry $BinDir

    Write-Host ""
    Write-Step "HiClaw uninstall complete"
    Write-Host "Open a new PowerShell window if stale commands are still visible."
}

Main
