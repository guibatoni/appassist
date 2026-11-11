#requires -Version 5.1
<#
DUELTRACE local Windows builder and optional public binary release publisher.
NO GitHub Actions, Windows runner, CI workflow artifact, or PRIVATE release is
used. Customers are always anonymous. Only the maintainer publishing the file
needs GitHub CLI login and a trusted code-signing certificate.

Quick start (from a CLEAN checkout on Windows 10/11):
  powershell -NoProfile -ExecutionPolicy Bypass -File tools/release/publicar_cliente.ps1
  powershell -NoProfile -ExecutionPolicy Bypass -File tools/release/publicar_cliente.ps1 -Publish -CertificateThumbprint YOUR_40_HEX -ExpectedPublisherSubject "CN=..."
The first command produces a LOCAL unsigned developer ZIP, NOT for public
distribution. The second signs and verifies before creating the public release.
#>
param(
    [switch]$Publish,
    [string]$CertificateThumbprint="",
    [string]$ExpectedPublisherSubject=""
)
Set-StrictMode -Version Latest
$ErrorActionPreference="Stop"
$publicRepo="guibatoni/dueltrace-releases"
$assetName="DUELTRACE-WebUI-Windows-Preview.zip"
$workspace=(Resolve-Path (Join-Path $PSScriptRoot "../..")).Path

# Stage logs remain in dist/build-diagnostics (ignored by Git) and are
# never copied to the customer's ZIP. A failure reports the exact stage.
$script:BuildStep=0
$script:BuildLogDir=Join-Path $workspace "dist/build-diagnostics"
New-Item -ItemType Directory -Force -Path $script:BuildLogDir | Out-Null

function Invoke-Checked([string]$Command,[string[]]$CommandArgs) {
    $script:BuildStep++
    $argsText=($CommandArgs -join " ")
    $stage=("{0:D2}" -f $script:BuildStep)
    $log=Join-Path $script:BuildLogDir ("etapa-" + $stage + ".log")
    $headline="[ETAPA $stage] $Command $argsText"
    Write-Host ""
    Write-Host $headline -ForegroundColor Cyan
    [IO.File]::WriteAllText($log,$headline + [Environment]::NewLine,
        [Text.UTF8Encoding]::new($false))
    $prior=$ErrorActionPreference
    $code=1
    try {
        # Windows PowerShell 5.1 can turn native stderr into a terminating
        # NativeCommandError when the preference is Stop. Allow both streams
        # to be recorded and use the native process exit code as authority.
        $ErrorActionPreference="Continue"
        & $Command @CommandArgs 2>&1 | ForEach-Object {
            $line=([string]$_)
            Write-Host $line
            Add-Content -LiteralPath $log -Value $line -Encoding UTF8
        }
        $code=$LASTEXITCODE
    } catch {
        $message=([string]$_)
        Add-Content -LiteralPath $log -Value $message -Encoding UTF8
        Write-Host $message -ForegroundColor Red
        $code=1
    } finally {
        $ErrorActionPreference=$prior
    }
    if ($code -ne 0) {
        $summary=Join-Path $script:BuildLogDir "ULTIMA_FALHA.txt"
        $header="FALHA NA ETAPA $stage. Codigo: $code. Comando: $Command $argsText"
        $tail=@(Get-Content -LiteralPath $log -Tail 45 -ErrorAction SilentlyContinue)
        [IO.File]::WriteAllLines($summary,@($header,"",("Log: " + $log),"")+$tail,
            [Text.UTF8Encoding]::new($false))
        Write-Host ""
        Write-Host "============== ULTIMA FALHA ==============" -ForegroundColor Red
        $tail | ForEach-Object { Write-Host $_ }
        Write-Host "Etapa: $stage | Codigo: $code" -ForegroundColor Red
        Write-Host "Diagnostico: $summary" -ForegroundColor Yellow
        Write-Host "==========================================" -ForegroundColor Red
        throw "Falha na etapa $stage: $Command $argsText (exit $code). Diagnostico: $summary"
    }
    Write-Host "[OK] Etapa $stage concluida." -ForegroundColor Green
}

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw "A compilação PyInstaller/WebView2 requer Windows, não Linux/macOS."
}
if ($Publish) {
    if ($CertificateThumbprint -cnotmatch '^[a-fA-F0-9]{40}$' -or
        [string]::IsNullOrWhiteSpace($ExpectedPublisherSubject)) {
        throw "Para publicar: forneça thumbprint Authenticode e Subject exato do editor."
    }
    if (!(Get-Command gh -ErrorAction SilentlyContinue)) {
        throw "Somente o proprietário precisa do GitHub CLI (gh auth login)."
    }
    Invoke-Checked "gh" @("auth","status")
}

Push-Location $workspace
$manifestPath=Join-Path $workspace "scanner/dueltrace-build.json"
$hadManifest=Test-Path -LiteralPath $manifestPath -PathType Leaf
$originalManifest=if ($hadManifest) {[IO.File]::ReadAllBytes($manifestPath)} else {$null}
try {
    # Prevent an uncommitted local modification from becoming an unreviewed
    # customer executable, and establish the exact private source identity.
    $sourceSha=(& git rev-parse HEAD).Trim().ToLowerInvariant()
    if ($LASTEXITCODE -ne 0 -or $sourceSha -cnotmatch '^[a-f0-9]{40}$') {
        throw "Commit local inválido."
    }
    $origin=(& git remote get-url origin).Trim()
    $trustedOrigin=(
        $origin -cmatch '^https://github\.com/guibatoni/appassist(\.git)?$' -or
        $origin -cmatch '^git@github\.com:guibatoni/appassist(\.git)?$' -or
        $origin -cmatch '^ssh://git@github\.com/guibatoni/appassist(\.git)?$'
    )
    if ($LASTEXITCODE -ne 0 -or !$trustedOrigin) {
        throw "Origem do código deve ser github.com/guibatoni/appassist (privado)."
    }
    $dirty=(& git status --porcelain)
    if ($LASTEXITCODE -ne 0 -or $dirty) {
        throw "Há alterações locais não commitadas. Publique apenas código revisado."
    }
    $env:PYTHONPATH=Join-Path $workspace "scanner"
    $version=(& python -c "from dueltrace_update_checker import CURRENT_VERSION; print(CURRENT_VERSION)").Trim()
    if ($LASTEXITCODE -ne 0 -or $version -cnotmatch '^[0-9]{1,4}\.[0-9]{1,4}\.[0-9]{1,4}$') {
        throw "Versão atual não identificada."
    }
    # Timestamp UTC is a monotonic, unique local build ID within the same
    # semver, compatible with the previously published GitHub Actions run IDs.
    $buildId=[long][DateTime]::UtcNow.ToString("yyyyMMddHHmmss")
    if ($buildId -ge 1000000000000000) { throw "Build ID muito grande." }
    $tag="preview-v$version-r$buildId"
    Write-Host "DUELTRACE local: $tag | fonte privada $sourceSha"
    $env:DUELTRACE_SOURCE_SHA=$sourceSha

    Invoke-Checked "python" @("-m","pip","install","-r","tools/security/requirements-webui-build.txt","pip-audit")
    Invoke-Checked "python" @("-m","pip_audit","--local")
    Invoke-Checked "python" @("-m","unittest","discover","-s","tests","-p","test_*.py","-v")
    Push-Location (Join-Path $workspace "web")
    try {
        Invoke-Checked "npm.cmd" @("ci")
        Invoke-Checked "npm.cmd" @("audit","--omit=dev","--audit-level=moderate")
        Invoke-Checked "npm.cmd" @("audit","--audit-level=high")
        Invoke-Checked "npm.cmd" @("run","build")
    } finally { Pop-Location }
    Invoke-Checked "python" @("tools/security/verify_web_css.py")

    $requiredPages=@(
        "web/out/index.html","web/out/inicio/index.html",
        "web/out/mods/index.html","web/out/biblioteca/index.html",
        "web/out/fusoes/index.html","web/out/drops/index.html",
        "web/out/ferramentas/calculadora/index.html",
        "web/out/ferramentas/fusoes/index.html"
    )
    foreach ($file in $requiredPages) {
        if (!(Test-Path -LiteralPath $file -PathType Leaf)) {
            throw "A compilação não incluiu tela obrigatória: $file"
        }
    }
    $identity=@{
        schema=1
        run_id=$buildId
        head_sha=$sourceSha
        version=$version
    } | ConvertTo-Json -Compress
    [IO.File]::WriteAllText($manifestPath,$identity,[Text.UTF8Encoding]::new($false))

    Invoke-Checked "python" @("-m","PyInstaller","--noconfirm","--clean","--onedir","--noconsole",
        "--name","DUELTRACE-WebUI","--paths","scanner","--collect-all","webview",
        "--add-data","web/out;web/out",
        "--add-data","scanner/dueltrace-build.json;.",
        "scanner/dueltrace_web_desktop.py")
    $dir=Join-Path $workspace "dist/DUELTRACE-WebUI"
    $exe=Join-Path $dir "DUELTRACE-WebUI.exe"
    if (!(Test-Path -LiteralPath $exe -PathType Leaf)) {
        throw "PyInstaller não gerou o executável Windows."
    }
    if ($Publish) {
        $certificate=Get-Item -LiteralPath "Cert:\CurrentUser\My\$CertificateThumbprint" -ErrorAction SilentlyContinue
        if (!$certificate -or !$certificate.HasPrivateKey -or
            $certificate.Subject -cne $ExpectedPublisherSubject -or
            $certificate.NotAfter -lt [DateTime]::Now) {
            throw "Certificado de editor inexistente, expirado ou não correspondente."
        }
        $sdk=Join-Path ([Environment]::GetFolderPath("ProgramFilesX86")) "Windows Kits\10\bin"
        $signtool=Get-ChildItem -LiteralPath $sdk -Recurse -File -Filter "signtool.exe" |
            Where-Object { $_.FullName -match '\\x64\\signtool\.exe$' } |
            Sort-Object FullName -Descending |
            Select-Object -First 1 -ExpandProperty FullName
        if (!$signtool) { throw "Windows SDK signtool.exe indisponível." }
        # Certificate stays in the Windows certificate store, never in a file
        # or in the public ZIP. Timestamping and trusted chain are mandatory.
        Invoke-Checked $signtool @("sign","/fd","SHA256","/sha1",
            $CertificateThumbprint,"/tr","http://timestamp.digicert.com",
            "/td","SHA256",$exe)
        $signature=Get-AuthenticodeSignature -LiteralPath $exe
        if ($signature.Status -ne "Valid" -or !$signature.SignerCertificate -or
            $signature.SignerCertificate.Subject -cne $ExpectedPublisherSubject -or
            $signature.SignerCertificate.Thumbprint.ToUpperInvariant() -ne $CertificateThumbprint.ToUpperInvariant()) {
            throw "Assinatura Authenticode do EXE não foi aprovada."
        }
        Copy-Item "tools/security/AVISO-ATUALIZACAO-CLIENTES.txt" (Join-Path $dir "LEIA-ME-ATUALIZACAO.txt") -Force
    } else {
        Copy-Item "tools/security/AVISO-SEGURANCA-PREVIEW.txt" (Join-Path $dir "LEIA-ME-SEGURANCA.txt") -Force
    }
    $zip=Join-Path $workspace "dist/$assetName"
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
    Compress-Archive -Path (Join-Path $dir "*") -DestinationPath $zip
    Invoke-Checked "python" @("tools/security/audit_windows_archive.py",
        $dir,$zip,"--report","dist/security/archive-integrity.json")
    $gateArgs=@("-PackageDirectory",$dir,"-ZipPath",$zip,
                "-OutputDirectory","dist/security")
    if ($Publish) {
        $gateArgs+=@("-RequireSignature","-ExpectedPublisherSubject",
                    $ExpectedPublisherSubject)
    }
    & (Join-Path $workspace "tools/security/gate_windows_package.ps1") @gateArgs
    if ($LASTEXITCODE -and $LASTEXITCODE -ne 0) { throw "Auditoria Defender falhou." }
    $digest=(Get-FileHash -LiteralPath $zip -Algorithm SHA256).Hash.ToLowerInvariant()
    $size=(Get-Item -LiteralPath $zip).Length
    Write-Host "ZIP LOCAL validado: $zip ($size bytes) SHA-256 $digest"

    if (!$Publish) {
        Write-Warning "Preview local NÃO ASSINADA: não distribuir a clientes. Para link público use -Publish com certificado válido."
        return
    }

    # Upload authentication belongs ONLY on the maintainer machine. The
    # app's update checker uses anonymous HTTPS against a public binary repo.
    $public=(& gh api "repos/$publicRepo") | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or !$public -or $public.private -or
        $public.full_name -cne $publicRepo) {
        throw "Crie primeiro $publicRepo como repositório PUBLICO com branch main. O código appassist fica privado."
    }
    if ($public.default_branch -notmatch '^[A-Za-z0-9][A-Za-z0-9._/-]*$') {
        throw "Branch padrão do repositório público não é válida."
    }
    $notes=(Get-Content "docs/DUELTRACE_UPDATE_NOTES.md" -Raw -Encoding UTF8).Trim()
    $notes+=[Environment]::NewLine+[Environment]::NewLine+"DUELTRACE Windows assinado. Binário somente; código-fonte privado."
    $notes+=[Environment]::NewLine+[Environment]::NewLine+"Build $buildId | Commit $sourceSha | SHA-256 ZIP: $digest"
    $notesPath=Join-Path $env:TEMP "dueltrace-release-$buildId.md"
    try {
        [IO.File]::WriteAllText($notesPath,$notes,[Text.UTF8Encoding]::new($false))
        # Do not make an unverified upload public: create a DRAFT first.
        Invoke-Checked "gh" @("release","create",$tag,$zip,"--repo",$publicRepo,
            "--target",$public.default_branch,
            "--title","DUELTRACE v$version Windows - Build $buildId",
            "--notes-file",$notesPath,"--draft","--prerelease")
    } finally {
        Remove-Item -LiteralPath $notesPath -Force -ErrorAction SilentlyContinue
    }

    $verified=$false
    for ($attempt=0; $attempt -lt 8; $attempt++) {
        $draft=(& gh api "repos/$publicRepo/releases/tags/$tag") | ConvertFrom-Json
        if ($LASTEXITCODE -ne 0 -or !$draft -or !$draft.draft) {
            throw "A release de verificação não existe como rascunho."
        }
        $assets=@($draft.assets | Where-Object { $_.name -eq $assetName })
        if ($assets.Count -eq 1 -and $assets[0].size -eq $size -and
            $assets[0].digest -ceq "sha256:$digest") {
            $verified=$true
            break
        }
        Start-Sleep -Seconds 3
    }
    if (!$verified) {
        throw "Digest do ZIP não confirmado; release permanece em RASCUNHO."
    }
    Invoke-Checked "gh" @("release","edit",$tag,"--repo",$publicRepo,
        "--draft=false","--prerelease","--latest=false")
    $published=(& gh api "repos/$publicRepo/releases/tags/$tag") | ConvertFrom-Json
    if ($LASTEXITCODE -ne 0 -or !$published -or $published.draft) {
        throw "A release assinada não ficou pública."
    }
    $asset=@($published.assets | Where-Object { $_.name -eq $assetName })
    if ($asset.Count -ne 1 -or $asset[0].size -ne $size -or
        $asset[0].digest -cne "sha256:$digest") {
        throw "A release pública diverge do ZIP verificado."
    }
    $link="https://github.com/$publicRepo/releases/download/$tag/$assetName"
    Write-Host "DOWNLOAD DIRETO (sem login para clientes): $link"
} finally {
    if ($hadManifest) {
        [IO.File]::WriteAllBytes($manifestPath,$originalManifest)
    } elseif (Test-Path -LiteralPath $manifestPath) {
        Remove-Item -LiteralPath $manifestPath -Force
    }
    Pop-Location
}
