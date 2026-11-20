$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
$python = Join-Path $PSScriptRoot 'runtime\venv\Scripts\python.exe'
if (!(Test-Path $python)) {
    if (!(Get-Command py -ErrorAction SilentlyContinue)) {
        throw 'Python 3.11+ with the py launcher is required.'
    }
    py -3 -m venv (Join-Path $PSScriptRoot 'runtime\venv')
    & $python -m pip install --disable-pip-version-check frida==16.7.19 certifi
}
& $python (Join-Path $PSScriptRoot 'deploy\windows_runtime.py') @args
exit $LASTEXITCODE
