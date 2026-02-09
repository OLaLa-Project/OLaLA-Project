$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$flutterBat = "C:\\Users\\alber\\sdks\\flutter\\bin\\flutter.bat"
if (-not (Test-Path $flutterBat)) {
  throw ("flutter.bat not found: {0}" -f $flutterBat)
}

$yesFile = Join-Path $env:TEMP "flutter-android-licenses-yes.txt"
$lines = @()
for ($i = 0; $i -lt 200; $i += 1) { $lines += "y" }

# ASCII avoids any encoding surprises with cmd.exe input redirection.
Set-Content -LiteralPath $yesFile -Value $lines -Encoding Ascii

$cmd = ('"{0}" doctor --android-licenses < "{1}"' -f $flutterBat, $yesFile)
Write-Output $cmd

& cmd.exe /c $cmd
if ($LASTEXITCODE -ne 0) {
  throw ("flutter doctor --android-licenses failed (exit={0})" -f $LASTEXITCODE)
}
