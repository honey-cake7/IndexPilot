# Dot-source from a PowerShell terminal: . .\scripts\use_node.ps1
# Installs a checksum-verified, workspace-local Node. No global PATH/install changes.
$indexPilotRoot = Split-Path -Parent $PSScriptRoot
$indexPilotNodeVersion = 'v26.13.0'
$indexPilotNodeDir = Join-Path $indexPilotRoot ".tools/node-$indexPilotNodeVersion-win-x64"
if (-not (Test-Path -LiteralPath (Join-Path $indexPilotNodeDir 'node.exe'))) {
    $indexPilotTools = Join-Path $indexPilotRoot '.tools'
    New-Item -ItemType Directory -Path $indexPilotTools -Force | Out-Null
    $indexPilotArchiveName = "node-$indexPilotNodeVersion-win-x64.zip"
    $indexPilotArchivePath = Join-Path $indexPilotTools $indexPilotArchiveName
    Invoke-WebRequest -Uri "https://nodejs.org/dist/$indexPilotNodeVersion/$indexPilotArchiveName" -OutFile $indexPilotArchivePath
    $indexPilotChecksums = (Invoke-WebRequest -Uri "https://nodejs.org/dist/$indexPilotNodeVersion/SHASUMS256.txt").Content
    $indexPilotExpected = (($indexPilotChecksums -split "`n" | Where-Object { $_ -match "  $([regex]::Escape($indexPilotArchiveName))\s*$" }) -split '\s+')[0]
    $indexPilotActual = (Get-FileHash -Algorithm SHA256 -LiteralPath $indexPilotArchivePath).Hash
    if (-not $indexPilotExpected -or $indexPilotExpected.ToLower() -ne $indexPilotActual.ToLower()) { throw 'Node release checksum mismatch' }
    Expand-Archive -LiteralPath $indexPilotArchivePath -DestinationPath $indexPilotTools -Force
}
$env:Path = $indexPilotNodeDir + ';' + $env:Path
