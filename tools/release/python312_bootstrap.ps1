#requires -Version 5.1
<#
Choose CPython 3.12 without changing the user's default Python (e.g. 3.14).
Create a project-local, ignored virtual environment. The local build scripts
run in this interpreter; customers never need Python or any GitHub login.
On systems without 3.12, install it using official winget Python.Python.3.12
in USER scope, then create the local virtual environment.
#>
param([switch]$NoInstall)

Set-StrictMode -Version Latest
$ErrorActionPreference="Stop"
$root=(Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$venv=Join-Path $root ".dueltrace-build-py312"
$venvPython=Join-Path $venv "Scripts\python.exe"

function Test-Python312([string]$Executable,[string[]]$Prefix=@()) {
    try {
        $found=& $Executable @Prefix -c "import sys; print(sys.executable if sys.version_info[:2] == (3, 12) else '')" 2>$null
        if ($LASTEXITCODE -ne 0 -or !$found) { return $null }
        $path=($found | Select-Object -Last 1).Trim()
        if ($path -and (Test-Path -LiteralPath $path -PathType Leaf)) {
            return (Resolve-Path -LiteralPath $path).Path
        }
    } catch {}
    return $null
}

function Find-Python312 {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        $found=Test-Python312 "py" @("-3.12")
        if ($found) { return $found }
    }
    if (Get-Command python3.12 -ErrorAction SilentlyContinue) {
        $found=Test-Python312 "python3.12"
        if ($found) { return $found }
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        $found=Test-Python312 "python"
        if ($found) { return $found }
    }
    $candidates=@()
    if ($env:LOCALAPPDATA) {
        $candidates+=Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"
    }
    if ($env:ProgramFiles) {
        $candidates+=Join-Path $env:ProgramFiles "Python312\python.exe"
    }
    $candidateFolders=@(
        "Registry::HKEY_CURRENT_USER\Software\Python\PythonCore\3.12\InstallPath",
        "Registry::HKEY_LOCAL_MACHINE\Software\Python\PythonCore\3.12\InstallPath"
    )
    foreach ($registryPath in $candidateFolders) {
        try {
            $base=(Get-Item -LiteralPath $registryPath -ErrorAction Stop).GetValue("")
            if ($base) { $candidates+=Join-Path $base "python.exe" }
        } catch {}
    }
    foreach ($candidate in $candidates) {
        if ((Test-Path -LiteralPath $candidate -PathType Leaf)) {
            $found=Test-Python312 $candidate
            if ($found) { return $found }
        }
    }
    return $null
}

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw "O ambiente de build exige Windows 10/11."
}

$existing=if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
    Test-Python312 $venvPython
} else { $null }
if ($existing) {
    Write-Host "Python 3.12 isolado já encontrado no projeto." -ForegroundColor Cyan
} else {
    if (Test-Path -LiteralPath $venv) {
        throw "A pasta .dueltrace-build-py312 existe, mas não contém um Python 3.12 válido. Preserve os dados e examine-a antes de recriar."
    }
    $selected=Find-Python312
    if (!$selected -and !$NoInstall) {
        if (!(Get-Command winget -ErrorAction SilentlyContinue)) {
            throw "Python 3.12 ausente. Instale-o pelo instalador oficial python.org ou ative winget e execute novamente; o Python 3.14 pode permanecer instalado."
        }
        Write-Host "Python 3.12 não encontrado. Instalando Python 3.12 para o usuário atual via winget..." -ForegroundColor Yellow
        & winget install --exact --id Python.Python.3.12 --source winget --scope user --silent --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) {
            throw "winget não concluiu a instalação do Python 3.12. Confira o acesso à internet e execute novamente."
        }
        $selected=Find-Python312
    }
    if (!$selected) {
        throw "Python 3.12 não encontrado. Instale Python 3.12 sem desinstalar o Python 3.14 e execute novamente."
    }
    Write-Host "Preparando ambiente Python 3.12 do DUELTRACE: $venv" -ForegroundColor Cyan
    & $selected -m venv $venv
    if ($LASTEXITCODE -ne 0) {
        throw "Não foi possível criar o ambiente virtual Python 3.12."
    }
    $existing=Test-Python312 $venvPython
    if (!$existing) {
        throw "O ambiente virtual criado não utiliza Python 3.12."
    }
}

# Environment changes only affect THIS PowerShell build session. They do not
# change the user's Windows PATH, registry, default Python or installed 3.14.
if ($env:PYTHONHOME) { Remove-Item Env:PYTHONHOME }
$venvScripts=Join-Path $venv "Scripts"
if (!$env:PATH.StartsWith("$venvScripts;",[StringComparison]::OrdinalIgnoreCase)) {
    $env:PATH="$venvScripts;$env:PATH"
}
$env:VIRTUAL_ENV=$venv
$actual=(& python -c "import sys; print('.'.join(map(str,sys.version_info[:3])))").Trim()
if ($LASTEXITCODE -ne 0 -or $actual -notmatch '^3\.12\.') {
    throw "O Python isolado não foi ativado corretamente (encontrado: $actual)."
}
Write-Host "Python $actual pronto (ambiente isolado). Python 3.14 do Windows não foi alterado." -ForegroundColor Green
