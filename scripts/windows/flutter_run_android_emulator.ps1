param(
  [ValidateSet("dev", "dev_android", "dev_emulator", "beta", "prod")]
  [string]$EnvName = "dev_android",
  [ValidateSet("debug", "profile", "release")]
  [string]$Mode = "debug",
  [string]$DeviceId = "emulator-5554"
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()

$adbExe = "C:\\Users\\alber\\AppData\\Local\\Android\\Sdk\\platform-tools\\adb.exe"
if (-not (Test-Path $adbExe)) {
  # Fallback to PATH (Android Studio installs typically add it, but not guaranteed).
  $adbExe = "adb"
}

$flutterBat = "C:\\Users\\alber\\sdks\\flutter\\bin\\flutter.bat"
if (-not (Test-Path $flutterBat)) {
  throw ("flutter.bat not found: {0}" -f $flutterBat)
}

$projectDir = "C:\\Users\\alber\\Desktop\\OLaLA-Production-v2\\apps\\flutter"
if (-not (Test-Path $projectDir)) {
  throw ("Flutter project dir not found: {0}" -f $projectDir)
}

Set-Location $projectDir

# NOTE:
# - Android Emulator's "host loopback" is 10.0.2.2, so `dev_android` uses that.
# - When VM service attach is flaky, try: `-Mode release` (no debug service protocol).
# - In some Windows+WSL setups, `10.0.2.2:8080` can time out. Use `dev_emulator` + adb reverse.
$envFile = ("config/env/{0}.json" -f $EnvName)
if (-not (Test-Path $envFile)) {
  throw ("env file not found: {0}" -f $envFile)
}

$adbReverseDone = $false
if ($EnvName -eq "dev_emulator") {
  try {
    & $adbExe -s $DeviceId reverse tcp:8080 tcp:8080 | Out-Null
    $adbReverseDone = $true
  } catch {
    Write-Host ("[warn] adb reverse failed. Try running manually: adb -s {0} reverse tcp:8080 tcp:8080" -f $DeviceId)
  }
}

$flutterArgs = @("run", "-d", $DeviceId, "--dart-define-from-file=$envFile")
if ($Mode -eq "profile") {
  $flutterArgs += "--profile"
} elseif ($Mode -eq "release") {
  $flutterArgs += "--release"
}

if ($adbReverseDone) {
  Write-Host "[info] adb reverse enabled: device 127.0.0.1:8080 -> host 127.0.0.1:8080"
}

& $flutterBat @flutterArgs
if ($LASTEXITCODE -ne 0) {
  throw ("flutter run failed (exit={0})" -f $LASTEXITCODE)
}
