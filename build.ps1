# FaceTracker Nuitka C-Compilation Build Script
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "  FaceTracker - Nuitka C-Compilation Standalone Packaging" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Detect Python path
$python = "D:/Program Files/Python/python.exe"
if (-not (Test-Path $python)) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) {
        $python = $cmd.Source
    } else {
        Write-Error "Python executable not found."
        exit 1
    }
}
Write-Host "[1/4] Using Python: $python" -ForegroundColor Green

# 2. Check Nuitka
& $python -m nuitka --version
if ($LASTEXITCODE -ne 0) {
    Write-Error "Nuitka compiler is not available."
    exit 1
}

# 3. Clean previous dist folder
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
if (-not $scriptDir) { $scriptDir = (Get-Location).Path }
$distBase = Join-Path $scriptDir "dist"
if (Test-Path $distBase) {
    Write-Host "[2/4] Cleaning previous build directory..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $distBase -ErrorAction SilentlyContinue
}

# 4. Run Nuitka C-compilation
Write-Host "[3/4] C-compilation in progress. Please wait..." -ForegroundColor Cyan

$nuitkaArgs = @(
    "-m", "nuitka",
    "--standalone",
    "--enable-plugin=pyside6",
    "--windows-console-mode=disable",
    "--output-dir=dist",
    "--output-filename=FaceTracker.exe",
    "--windows-icon-from-ico=facetracker.ico",
    "--assume-yes-for-downloads",
    "--jobs=2",
    "--nofollow-import-to=tkinter,unittest,pytest,pydoc,sqlite3,IPython,jupyter,matplotlib,scipy,mediapipe",
    "main.py"
)

& $python $nuitkaArgs
if ($LASTEXITCODE -ne 0) {
    Write-Error "Nuitka FaceTracker compilation failed."
    exit $LASTEXITCODE
}

# 5. Copy model and config files
Write-Host "[4/4] Bundling ONNX model and config files into dist..." -ForegroundColor Cyan

$targetDist = Join-Path $distBase "main.dist"
if (-not (Test-Path $targetDist)) {
    $altDist = Join-Path $distBase "FaceTracker.dist"
    if (Test-Path $altDist) {
        $targetDist = $altDist
    }
}

if (Test-Path $targetDist) {
    $modelFile = Join-Path $scriptDir "face_detection_yunet_2023mar.onnx"
    if (Test-Path $modelFile) {
        Copy-Item -Path $modelFile -Destination $targetDist -Force
        Write-Host "  -> Bundled model: $modelFile" -ForegroundColor Gray
    }
    
    $configFile = Join-Path $scriptDir "facetracker_config.json"
    if (Test-Path $configFile) {
        Copy-Item -Path $configFile -Destination $targetDist -Force
        Write-Host "  -> Bundled config: $configFile" -ForegroundColor Gray
    }

    $cbConfigFile = Join-Path $scriptDir "clickbar_config.json"
    if (Test-Path $cbConfigFile) {
        Copy-Item -Path $cbConfigFile -Destination $targetDist -Force
        Write-Host "  -> Bundled ClickBar config: $cbConfigFile" -ForegroundColor Gray
    }

    # Compile ClickBar.exe GUI launcher with zig
    $zigPath = Join-Path $env:LOCALAPPDATA "Nuitka\Nuitka\Cache\downloads\pip\private-2b96c5fc\Lib\site-packages\ziglang\zig.exe"
    $cSrc = Join-Path $scriptDir "launcher\clickbar_launcher.c"
    $rcSrc = Join-Path $scriptDir "launcher\clickbar.rc"
    $cbOut = Join-Path $targetDist "ClickBar.exe"
    if ((Test-Path $zigPath) -and (Test-Path $cSrc)) {
        & $zigPath cc -target x86_64-windows-gnu $cSrc $rcSrc -o $cbOut -lshlwapi -Wl,--subsystem,windows
        Write-Host "  -> Compiled standalone GUI launcher: $cbOut" -ForegroundColor Gray
    }

    $finalDist = Join-Path $distBase "FaceTracker"
    if ($targetDist -ne $finalDist) {
        Rename-Item -Path $targetDist -NewName "FaceTracker" -Force -ErrorAction SilentlyContinue
        if (Test-Path $finalDist) {
            $targetDist = $finalDist
        }
    }

    # Clean intermediate build cache
    $buildCache = Join-Path $distBase "main.build"
    if (Test-Path $buildCache) {
        Remove-Item -Recurse -Force $buildCache -ErrorAction SilentlyContinue
    }

    Write-Host ""
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "  [SUCCESS] C-compiled standalone distribution ready!" -ForegroundColor Green
    Write-Host "  Executable location: $targetDist\FaceTracker.exe" -ForegroundColor White
    Write-Host "==========================================================" -ForegroundColor Green
} else {
    Write-Warning "Could not find target dist folder."
}
