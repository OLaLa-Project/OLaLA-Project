$ErrorActionPreference = "Stop"

# Install "Android SDK Command-line Tools (latest)" into:
#   %LOCALAPPDATA%\Android\Sdk\cmdline-tools\latest
#
# This unblocks `flutter doctor` and `flutter doctor --android-licenses` on Windows.

[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$repoXmlUrl = "https://dl.google.com/android/repository/repository2-1.xml"
$repoBaseUrl = "https://dl.google.com/android/repository/"

$sdkRoot = Join-Path $env:LOCALAPPDATA "Android\\Sdk"
$cmdlineToolsRoot = Join-Path $sdkRoot "cmdline-tools"
$latestDir = Join-Path $cmdlineToolsRoot "latest"

Write-Output ("SDK root: {0}" -f $sdkRoot)

$null = New-Item -ItemType Directory -Force -Path $sdkRoot
$null = New-Item -ItemType Directory -Force -Path $cmdlineToolsRoot

Write-Output "Downloading repository index..."
$repoXml = (Invoke-WebRequest -Uri $repoXmlUrl -UseBasicParsing -TimeoutSec 120).Content

[xml]$doc = $repoXml

$pkgNode = $doc.SelectSingleNode("//*[local-name()='remotePackage' and @path='cmdline-tools;latest']")
if (-not $pkgNode) {
  throw "remotePackage path='cmdline-tools;latest' not found in repository XML"
}

$urlNode = $pkgNode.SelectSingleNode(".//*[local-name()='archive'][.//*[local-name()='host-os' and normalize-space(text())='windows']]//*[local-name()='complete']//*[local-name()='url']")
if (-not $urlNode) {
  throw "Windows archive URL not found for cmdline-tools;latest"
}

$relUrl = $urlNode.InnerText.Trim()
if ([string]::IsNullOrWhiteSpace($relUrl)) {
  throw "Empty archive URL for cmdline-tools;latest"
}

$fileName = [System.IO.Path]::GetFileName($relUrl)
$downloadUrl = $repoBaseUrl + $relUrl

Write-Output ("Resolved cmdline-tools archive: {0}" -f $fileName)

$zipPath = Join-Path $env:TEMP $fileName
$extractRoot = Join-Path $env:TEMP ("android-cmdline-tools-" + [Guid]::NewGuid().ToString("N"))

Write-Output "Downloading cmdline-tools zip..."
Invoke-WebRequest -Uri $downloadUrl -OutFile $zipPath -UseBasicParsing -TimeoutSec 1200

Write-Output "Extracting..."
$null = New-Item -ItemType Directory -Force -Path $extractRoot
Expand-Archive -LiteralPath $zipPath -DestinationPath $extractRoot -Force

$extractedDir = Join-Path $extractRoot "cmdline-tools"
if (-not (Test-Path $extractedDir)) {
  throw ("Unexpected archive layout: missing {0}" -f $extractedDir)
}

if (Test-Path $latestDir) {
  Write-Output ("Removing existing: {0}" -f $latestDir)
  Remove-Item -Recurse -Force -LiteralPath $latestDir
}

Write-Output ("Installing into: {0}" -f $latestDir)
Move-Item -LiteralPath $extractedDir -Destination $latestDir -Force

$sdkManager = Join-Path $latestDir "bin\\sdkmanager.bat"
if (-not (Test-Path $sdkManager)) {
  throw ("Install completed but sdkmanager.bat missing at: {0}" -f $sdkManager)
}

Write-Output ("OK: {0}" -f $sdkManager)

