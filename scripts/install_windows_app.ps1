# Install Meteor as a real Windows app for the current user.
# Creates a Start Menu shortcut + Desktop shortcut pointing at run.py.
$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python   = (Get-Command python.exe -ErrorAction SilentlyContinue).Source
if (-not $Python) { $Python = (Get-Command py.exe -ErrorAction SilentlyContinue).Source }
if (-not $Python) { throw "Python 3.11+ not found on PATH. Install from python.org first." }

$IconSrc = Join-Path $RepoRoot "assets\meteor_icon_256.png"
$IconDst = Join-Path $RepoRoot "assets\meteor.ico"

# Convert PNG → ICO with Add-Type (System.Drawing) — best-effort; falls back
# to the .png if conversion fails.
try {
  Add-Type -AssemblyName System.Drawing
  $img  = [System.Drawing.Image]::FromFile($IconSrc)
  $bmp  = New-Object System.Drawing.Bitmap $img, 256, 256
  $hIco = $bmp.GetHicon()
  $ico  = [System.Drawing.Icon]::FromHandle($hIco)
  $fs   = [System.IO.File]::Create($IconDst)
  $ico.Save($fs); $fs.Close()
  $iconPath = $IconDst
} catch {
  $iconPath = $IconSrc
}

function New-Shortcut($LinkPath, $Target, $Args, $WorkDir, $Icon) {
  $wsh = New-Object -ComObject WScript.Shell
  $sc  = $wsh.CreateShortcut($LinkPath)
  $sc.TargetPath       = $Target
  $sc.Arguments        = $Args
  $sc.WorkingDirectory = $WorkDir
  $sc.IconLocation     = $Icon
  $sc.Description      = "Local-first agentic AI runtime"
  $sc.Save()
}

$StartMenu = [Environment]::GetFolderPath("Programs")
$Desktop   = [Environment]::GetFolderPath("Desktop")
$RunPy     = Join-Path $RepoRoot "run.py"

foreach ($dir in @($StartMenu, $Desktop)) {
  New-Shortcut (Join-Path $dir "Meteor.lnk") $Python "`"$RunPy`"" $RepoRoot $iconPath
}

Write-Host "Meteor installed:"
Write-Host "  Start Menu: $StartMenu\Meteor.lnk"
Write-Host "  Desktop:    $Desktop\Meteor.lnk"
Write-Host "  Launcher:   $Python `"$RunPy`""
