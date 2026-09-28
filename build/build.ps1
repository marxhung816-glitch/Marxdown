param(
    [switch]$OneFile
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path -Parent $PSScriptRoot)
$mode = if ($OneFile) { "--onefile" } else { "--onedir" }

# Qt uses Windows' ICU API. Avoid picking up an incompatible ICU DLL from
# another application on PATH (for example Poppler) during PyInstaller analysis.
$system32 = (Resolve-Path "$env:SystemRoot\System32").Path.TrimEnd('\')
$safePaths = foreach ($entry in ($env:PATH -split ';')) {
    if ([string]::IsNullOrWhiteSpace($entry)) { continue }
    $folder = $entry.Trim('"')
    if ((Test-Path (Join-Path $folder 'icuuc.dll')) -and $folder.TrimEnd('\') -ine $system32) {
        continue
    }
    $entry
}
$env:PATH = $safePaths -join ';'

python -m PyInstaller --noconfirm --clean --windowed $mode `
    --name Marxdown `
    --icon "resources/icons/marxdown.ico" `
    --add-data "resources;resources" `
    --collect-submodules pygments.lexers `
    --exclude-module PySide6.QtQml `
    --exclude-module PySide6.QtQuick `
    --exclude-module PySide6.QtQuickWidgets `
    --exclude-module PySide6.QtQuickControls2 `
    --exclude-module lxml.isoschematron `
    main.py

if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
Write-Host "Build complete: dist/Marxdown/Marxdown.exe (one-file mode: dist/Marxdown.exe)"
