#requires -Version 5.1
<#
DUELTRACE Windows build Python selector.
Use an already installed CPython 3.14 (preferred) or 3.12; NEVER download or
install another Python, change system PATH, or remove the user's Python.
Create an isolated project-local venv for dependencies and PyInstaller.
#>
param()
Set-StrictMode -Version Latest
$ErrorActionPreference="Stop"
$root=(Resolve-Path (Join-Path $PSScriptRoot "../..")).Path

function Test-Interpreter([string]$Command,[string[]]$Prefix=@()) {
    try {
        $result=@(& $Command @Prefix -c "import sys; print(str(sys.version_info.major) + '.' + str(sys.version_info.minor) + '|' + sys.executable)" 2>$null)
        if ($LASTEXITCODE -ne 0 -or $result.Count -eq 0) { return $null }
        $last=([string]$result[-1]).Trim()
        if ($last -notmatch '^(3\.(?:14|12))\|(.+)$') { return $null }
        $version=$Matches[1]
        $path=$Matches[2]
        if (!(Test-Path -LiteralPath $path -PathType Leaf)) { return $null }
        return @{Version=$version; Path=(Resolve-Path -LiteralPath $path).Path}
    } catch {
        return $null
    }
}

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw "A compilação do DUELTRACE exige Windows 10 ou 11."
}

$candidates=@()
$python=Get-Command python -ErrorAction SilentlyContinue
if ($python) { $candidates += @{Command="python"; Args=@()} }
$py=Get-Command py -ErrorAction SilentlyContinue
if ($py) {
    $candidates += @{Command="py"; Args=@("-3.14")}
    $candidates += @{Command="py"; Args=@("-3.12")}
}
if (Get-Command python3.14 -ErrorAction SilentlyContinue) {
    $candidates += @{Command="python3.14"; Args=@()}
}
if (Get-Command python3.12 -ErrorAction SilentlyContinue) {
    $candidates += @{Command="python3.12"; Args=@()}
}
if ($env:LOCALAPPDATA) {
    $candidates += @{Command=(Join-Path $env:LOCALAPPDATA "Programs\Python\Python314\python.exe"); Args=@()}
    $candidates += @{Command=(Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"); Args=@()}
}
if ($env:ProgramFiles) {
    $candidates += @{Command=(Join-Path $env:ProgramFiles "Python314\python.exe"); Args=@()}
    $candidates += @{Command=(Join-Path $env:ProgramFiles "Python312\python.exe"); Args=@()}
}

$selected=$null
foreach ($candidate in $candidates) {
    $found=Test-Interpreter $candidate.Command $candidate.Args
    if ($found) {
        if (!$selected -or ($found.Version -eq "3.14" -and $selected.Version -ne "3.14")) {
            $selected=$found
        }
    }
}
if (!$selected) {
    throw "Não encontrei CPython 3.14 ou 3.12 instalado. Este kit NÃO instala outro Python."
}
$code=$selected.Version.Replace(".","")
$venv=Join-Path $root ".dueltrace-build-py$code"
$pythonInVenv=Join-Path $venv "Scripts\python.exe"
if (Test-Path -LiteralPath $venv) {
    if (!(Test-Path -LiteralPath $pythonInVenv -PathType Leaf)) {
        throw "Pasta de ambiente incompleta: $venv. Renomeie-a após verificar seu conteúdo."
    }
} else {
    Write-Host "Criando ambiente privado do DUELTRACE com Python $($selected.Version)..." -ForegroundColor Cyan
    & $selected.Path -m venv $venv
    if ($LASTEXITCODE -ne 0) {
        throw "Falha na criação do ambiente virtual com o Python já instalado."
    }
}
$venvInfo=Test-Interpreter $pythonInVenv
if (!$venvInfo -or $venvInfo.Version -ne $selected.Version) {
    throw "O ambiente virtual do DUELTRACE não corresponde ao Python selecionado."
}
# Changes are confined to the build process. Default Windows Python is intact.
if ($env:PYTHONHOME) { Remove-Item Env:PYTHONHOME }
$bin=Join-Path $venv "Scripts"
$env:PATH="$bin;$env:PATH"
$env:VIRTUAL_ENV=$venv
$actual=@(& python -c "import sys; print(str(sys.version_info.major) + '.' + str(sys.version_info.minor))" 2>$null)
if ($LASTEXITCODE -ne 0 -or [string]$actual[-1] -cne $selected.Version) {
    throw "O interpretador do ambiente virtual não foi ativado."
}
Write-Host "DUELTRACE: Python $($selected.Version) isolado e pronto." -ForegroundColor Green
Write-Host "Nenhum Python adicional foi instalado e o Python padrão foi preservado."
