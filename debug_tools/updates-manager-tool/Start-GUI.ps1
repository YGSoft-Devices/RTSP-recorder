# Updates Manager Tool Launcher
$toolDir = $PSScriptRoot
Push-Location $toolDir
try {
    & ".\.venv\Scripts\python.exe" "run.py" $args
} finally {
    Pop-Location
}
