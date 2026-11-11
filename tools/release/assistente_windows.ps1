#requires -Version 5.1
<#
Interactive helper for the DUELTRACE developer on Windows.
Never distributes source code, ISOs, GitHub credentials or signing keys.
The public ZIP is produced only by tools/release/publicar_cliente.ps1
after tests, Authenticode signature and Microsoft Defender validation.
#>
param(
    [ValidateSet("Verificar","Compilar","Publicar","PrepararCanal")]
    [string]$Acao="Verificar"
)
Set-StrictMode -Version Latest
$ErrorActionPreference="Stop"
$root=(Resolve-Path (Join-Path $PSScriptRoot "../..")).Path
$publisher=Join-Path $PSScriptRoot "publicar_cliente.ps1"
$destination="guibatoni/dueltrace-releases"

function Require-Command([string]$name,[string]$explanation) {
    if (!(Get-Command $name -ErrorAction SilentlyContinue)) {
        throw "Falta $name. $explanation"
    }
}
function Check-Windows {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
        throw "A compilação do DUELTRACE.exe é suportada somente no Windows."
    }
}
function Check-Tools {
    Check-Windows
    Require-Command "git" "Instale Git para Windows."
    Require-Command "node" "Utilize o Node.js já instalado (22, 24 ou 26)."
    Require-Command "npm.cmd" "Reinstale Node.js/npm."
    if (!(Test-Path -LiteralPath $publisher -PathType Leaf) -or
        !(Test-Path -LiteralPath (Join-Path $root "web/package-lock.json"))) {
        throw "Abra o kit junto ao código privado completo do DUELTRACE."
    }
    # Accept the user's installed Python 3.14.6 (or 3.12) in a local venv.
    # Do not install another interpreter or change the default Windows Python.
    $pythonBootstrap=Join-Path $PSScriptRoot "python_build_bootstrap.ps1"
    if (!(Test-Path -LiteralPath $pythonBootstrap -PathType Leaf)) {
        throw "Atualize a branch do DUELTRACE: seletor do Python instalado ausente."
    }
    & $pythonBootstrap
    $version=(& python -c "import sys; print('.'.join(map(str,sys.version_info[:3])))").Trim()
    if ($LASTEXITCODE -ne 0 -or $version -notmatch '^3\.(12|14)\.') {
        throw "Ambiente isolado incorreto: use Python 3.14 ou 3.12 já instalado (encontrado: $version)."
    }
    $nodeVersion=(& node --version).Trim()
    # Next.js 16 needs Node >=20.9. The supported current/LTS major
    # versions 22, 24 and 26 are accepted without changing the system.
    if ($LASTEXITCODE -ne 0 -or $nodeVersion -notmatch '^v(?:22|24|26)\.[0-9]+\.[0-9]+$') {
        throw "Node.js incompatível (encontrado: $nodeVersion). Use Node.js 22, 24 ou 26."
    }

    Write-Host "Ambiente do DUELTRACE: Python $version já instalado (isolado) e Node $nodeVersion."
}

function Check-Public-Repository([bool]$create) {
    Require-Command "gh" "Somente o publicador precisa do GitHub CLI."
    & gh auth status
    if ($LASTEXITCODE -ne 0) {
        throw "Autorize a conta de desenvolvimento: gh auth login"
    }
    $found=$null
    try {
        $raw=& gh api "repos/$destination" 2>$null
        if ($LASTEXITCODE -eq 0) { $found=($raw | ConvertFrom-Json) }
    } catch { $found=$null }
    if ($null -eq $found) {
        if (!$create) {
            throw "Repositório $destination não existe. Execute PREPARAR_CANAL_PUBLICO.cmd."
        }
        Write-Host "Será criado apenas um repositório vazio de BINÁRIOS PÚBLICOS." -ForegroundColor Yellow
        Write-Host "O código PRIVADO guibatoni/appassist não será enviado nem alterado." -ForegroundColor Yellow
        $confirm=Read-Host "Digite CRIAR para autorizar a criação do repositório público"
        if ($confirm -cne "CRIAR") { throw "Operação cancelada. Nenhum repositório criado." }
        & gh repo create $destination --public --add-readme --disable-wiki
        if ($LASTEXITCODE -ne 0) { throw "Não foi possível criar o repositório de binários." }
        $raw=& gh api "repos/$destination"
        if ($LASTEXITCODE -ne 0) { throw "Repositório criado, mas não foi possível validá-lo." }
        $found=$raw | ConvertFrom-Json
    }
    if ($found.full_name -cne $destination -or $found.private -ne $false) {
        throw "O canal deve ser exatamente $destination e ser público."
    }
    Write-Host "Canal de distribuição pública confirmado: https://github.com/$destination/releases" -ForegroundColor Green
}

Push-Location $root
try {
    if ($Acao -eq "PrepararCanal") {
        Check-Windows
        Check-Public-Repository $true
    } elseif ($Acao -eq "Verificar") {
        Check-Tools
        Write-Host "Dependências básicas encontradas. A compilação real executa mais testes." -ForegroundColor Green
        if (!(Get-Command "gh" -ErrorAction SilentlyContinue)) {
            Write-Host "GitHub CLI não instalado; necessário somente para publicar aos clientes."
        }
    } elseif ($Acao -eq "Compilar") {
        Check-Tools
        & $publisher
        if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "Falha na compilação Windows." }
        $zip=Join-Path $root "dist/DUELTRACE-WebUI-Windows-Preview.zip"
        if (!(Test-Path -LiteralPath $zip -PathType Leaf)) {
            throw "Compilador terminou sem gerar o ZIP."
        }
        Write-Host "Preview completa criada em: $zip" -ForegroundColor Green
        Write-Warning "Preview local sem assinatura: não publicar a clientes."
    } elseif ($Acao -eq "Publicar") {
        Check-Tools
        Check-Public-Repository $false
        $certificates=@(Get-ChildItem Cert:\CurrentUser\My | Where-Object {
            $_.HasPrivateKey -and $_.NotAfter -gt (Get-Date) -and
            @($_.EnhancedKeyUsageList | Where-Object {
                $_.ObjectId -eq "1.3.6.1.5.5.7.3.3"
            }).Count -gt 0
        })
        if ($certificates.Count -eq 0) {
            throw "Nenhum certificado Authenticode de assinatura de código válido com chave privada foi encontrado em Cert:\CurrentUser\My."
        }
        Write-Host "Certificados disponíveis para assinatura:"
        for ($i=0; $i -lt $certificates.Count; $i++) {
            Write-Host ("{0}. {1} | Válido até {2:yyyy-MM-dd} | {3}" -f
                ($i+1),$certificates[$i].Subject,$certificates[$i].NotAfter,
                $certificates[$i].Thumbprint)
        }
        $choice=Read-Host "Digite o número do certificado de editor"
        $number=0
        if (![int]::TryParse($choice,[ref]$number) -or $number -lt 1 -or
            $number -gt $certificates.Count) {
            throw "Certificado não selecionado."
        }
        $selected=$certificates[$number-1]
        & $publisher -Publish -CertificateThumbprint $selected.Thumbprint -ExpectedPublisherSubject $selected.Subject
        if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "Publicação interrompida." }
    }
} finally {
    Pop-Location
}
