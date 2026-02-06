# Updates Manager Tool CLI
$toolDir = $PSScriptRoot
Push-Location $toolDir
try {
    & ".\.venv\Scripts\python.exe" "-m" "app.cli" $args
} finally {
    Pop-Location
}
