param([string]$OutputDirectory = 'dist')
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$buildRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $OutputDirectory))
if (-not $buildRoot.StartsWith($PSScriptRoot + '\', [StringComparison]::OrdinalIgnoreCase)) {
    throw 'Build output must be inside the project.'
}
$applicationFolder = Join-Path $buildRoot 'AI Short Maker'
$applicationExe = Join-Path $applicationFolder 'AI Short Maker.exe'
$runningApp = Get-Process -Name 'AI Short Maker' -ErrorAction SilentlyContinue | Where-Object { $_.Path -eq $applicationExe }
if ($runningApp) { throw 'Close this build of AI Short Maker first, or supply a different -OutputDirectory.' }
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --distpath $buildRoot 'ShortMaker.spec'
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
foreach ($document in @('README.md','VALIDATION.md')) {
    Copy-Item -LiteralPath $document -Destination (Join-Path $applicationFolder $document)
}
Copy-Item -LiteralPath 'assets\THIRD-PARTY.md' -Destination (Join-Path $applicationFolder 'THIRD-PARTY.md')
$docsFolder = Join-Path $applicationFolder 'docs'
New-Item -ItemType Directory -Force -Path $docsFolder | Out-Null
foreach ($document in @('MRBEAST_RESEARCH.md')) {
    Copy-Item -LiteralPath (Join-Path 'docs' $document) -Destination (Join-Path $docsFolder $document)
}
Write-Host "Ready: $applicationExe"
