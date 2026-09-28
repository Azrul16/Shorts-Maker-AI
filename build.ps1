$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
& .\.venv\Scripts\python.exe -m PyInstaller --noconfirm 'ShortMaker.spec'
if ($LASTEXITCODE -ne 0) { throw 'EXE build failed.' }
Copy-Item -LiteralPath 'README.md' -Destination 'dist\AI Short Maker\README.md'
Copy-Item -LiteralPath 'assets\THIRD-PARTY.md' -Destination 'dist\AI Short Maker\THIRD-PARTY.md'
Copy-Item -LiteralPath 'VALIDATION.md' -Destination 'dist\AI Short Maker\VALIDATION.md'
New-Item -ItemType Directory -Force -Path 'dist\AI Short Maker\docs' | Out-Null
Copy-Item -LiteralPath 'docs\COMPETITIVE_RESEARCH.md' -Destination 'dist\AI Short Maker\docs\COMPETITIVE_RESEARCH.md'
Write-Host 'Ready: dist\AI Short Maker\AI Short Maker.exe'
