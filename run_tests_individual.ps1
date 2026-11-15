param(
    [switch]$StopOnFail
)

$ErrorActionPreference = 'Stop'

Write-Host 'Running tests individually (one file at a time)...' -ForegroundColor Cyan

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$testFiles = Get-ChildItem -Path ".\tests" -Filter "test_*.py" | Sort-Object Name

if (-not $testFiles) {
    Write-Host 'No test files found in .\tests' -ForegroundColor Yellow
    exit 1
}

$passed = 0
$failed = 0
$failedFiles = @()

foreach ($file in $testFiles) {
    Write-Host "`n=== Running $($file.Name) ===" -ForegroundColor Cyan

    & python -m pytest $file.FullName -v
    $exitCode = $LASTEXITCODE

    if ($exitCode -eq 0) {
        $passed += 1
        Write-Host "PASS: $($file.Name)" -ForegroundColor Green
    } else {
        $failed += 1
        $failedFiles += $file.Name
        Write-Host "FAIL: $($file.Name)" -ForegroundColor Red

        if ($StopOnFail) {
            Write-Host '`nStopped early because -StopOnFail was set.' -ForegroundColor Yellow
            break
        }
    }
}

Write-Host "`n===== Summary =====" -ForegroundColor White
Write-Host "Total files: $($testFiles.Count)"
Write-Host "Passed: $passed" -ForegroundColor Green
Write-Host "Failed: $failed" -ForegroundColor Red

if ($failedFiles.Count -gt 0) {
    Write-Host 'Failed files:' -ForegroundColor Red
    $failedFiles | ForEach-Object { Write-Host " - $_" -ForegroundColor Red }
    exit 1
}

Write-Host 'All individual test files passed.' -ForegroundColor Green
exit 0
